#!/usr/bin/env python3
"""Ofertas de MediaMarkt España. Python 3.10+, sin dependencias externas."""
import argparse
import csv
import html
import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

BASE = "https://www.mediamarkt.es"
SOURCES = {
    "Switch": BASE + "/es/category/juegos-nintendo-switch-855.html",
    "Switch 2": BASE + "/es/category/juegos-nintendo-switch-2-8550.html",
}
AGENT = "SwitchOffers/1.0"
VOID = set("area base br col embed hr img input link meta param source track wbr".split())


class Node:
    def __init__(self, tag="root", attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def nodes(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.nodes()

    def text(self):
        return " ".join(c.text() if isinstance(c, Node) else c for c in self.children)

    def find(self, test):
        return next((n for n in self.nodes() if n.attrs.get("data-test") == test), None)


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def amounts(text):
    # Exige símbolo €: evita confundir puntuaciones, porcentajes y cuotas.
    found = re.findall(r"(\d[\d.]*)(?:,\s*(\d{2}|[–—-]))?\s*€", text)
    return [int(a.replace(".", "")) * 100 + (int(b) if b.isdigit() else 0)
            for a, b in found]


def trusted(url):
    p = urlsplit(url)
    return p.scheme == "https" and p.netloc == "www.mediamarkt.es"


def paging(source):
    match = re.search(r'"currentPage":(\d+),"pageCount":(\d+),"pageSize":(\d+),"maxPage":(\d+)', source)
    return tuple(map(int, match.groups())) if match else None


def parse(source, platform):
    root = Document(source).root
    products = []
    cards = [n for n in root.nodes() if n.attrs.get("data-test") == "mms-product-card"]
    for card in cards:
        title = card.find("product-title")
        link = (card.find("mms-router-link-product-list-item-link")
                or card.find("mms-router-link-product-list-item-link_mp"))
        price_node = card.find("cofr-price product-price") or card.find("mms-price")
        if title is None or link is None or price_node is None:
            raise ValueError("Ficha no reconocida: " + (title.text()[:120] if title else "sin título"))
        name = " ".join(title.text().split())
        text = " ".join(card.text().split())
        # La categoría incluye ocasionalmente accesorios u otras plataformas.
        if not re.search(r"(?:Juego Nintendo Switch|Nintendo Switch(?: 2)?\b)", text, re.I):
            continue
        if not re.search(r"(?:Tipo de dispositivo Juego Nintendo Switch|Tipo de producto Software)", text, re.I):
            if re.search(r"(?:funda|protector|mando|consola|accesorio)", name, re.I):
                continue
        actual_platform = "Switch 2" if re.search(r"Nintendo Switch\s*2\b", name, re.I) else platform
        prices = amounts(price_node.text())
        if not prices:
            raise ValueError(f"Precio no reconocido: {name}")
        price = prices[-1]
        strike = next((n for n in price_node.nodes()
                       if n.attrs.get("data-test", "").startswith("mms-strike-price-type")), None)
        reference = amounts(strike.text())[0] if strike is not None and amounts(strike.text()) else None
        url = urljoin(BASE, link.attrs.get("href", ""))
        if not trusted(url) or "/es/product/" not in url:
            raise ValueError("Enlace de producto inesperado")
        delivery = card.find("product-delivery")
        delivery_text = " ".join(delivery.text().split()) if delivery is not None else "Desconocida"
        available = card.find("mms-cofr-delivery_AVAILABLE") is not None
        seller_node = card.find('mms-third-party-provider-link')
        seller = ' '.join(seller_node.text().split()) if seller_node else 'No especificado en listado'
        lower = name.lower()
        fmt = ("Game Key Card" if re.search(r"game[ -]?key", lower) else
               "Código" if re.search(r"c[oó]digo|code in|digital|descarga", lower) else
               "No especificado")
        products.append(dict(nombre=name, consola=actual_platform, precio_centimos=price,
            referencia_centimos=reference,
            descuento=round((1-price/reference)*100, 2) if reference and reference > price else 0,
            disponible_online=available, disponibilidad=delivery_text,
            vendedor=seller,
            formato=fmt, url=url))
    next_link = next((n.attrs.get("href") for n in root.nodes()
                      if n.tag == "link" and n.attrs.get("rel") == "next"), None)
    return products, urljoin(BASE, next_link) if next_link else None


def fetch(url):
    if not trusted(url):
        raise ValueError("Solo se permiten URLs de MediaMarkt España")
    request = Request(url, headers={"User-Agent": AGENT, "Accept-Language": "es-ES,es;q=0.9"})
    with urlopen(request, timeout=35) as response:
        if not trusted(response.url):
            raise ValueError("Redirección fuera de MediaMarkt")
        return response.read().decode("utf-8")


def robots():
    rp = RobotFileParser()
    try:
        rp.parse(fetch(BASE + "/robots.txt").splitlines())
    except HTTPError as e:
        if e.code == 404:
            rp.parse([])
        else:
            raise
    return rp


def history(products, database, stamp):
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE IF NOT EXISTS prices (url TEXT, stamp TEXT, price INTEGER, PRIMARY KEY(url,stamp))")
        for p in products:
            last = db.execute("SELECT price FROM prices WHERE url=? ORDER BY stamp DESC LIMIT 1", (p['url'],)).fetchone()
            low = db.execute("SELECT MIN(price) FROM prices WHERE url=?", (p['url'],)).fetchone()[0]
            p['anterior_centimos'] = last[0] if last else None
            p['bajada_centimos'] = max(0, last[0] - p['precio_centimos']) if last else 0
            p['minimo_observado_centimos'] = min(low, p['precio_centimos']) if low else p['precio_centimos']
            db.execute("INSERT INTO prices VALUES (?,?,?)", (p['url'], stamp, p['precio_centimos']))


def euro(cents):
    return f"{cents/100:.2f} €".replace('.', ',') if cents is not None else '—'


def report(products, target, stamp, warnings):
    esc = html.escape
    rows = []
    for p in products:
        fields = [f'<a href="{esc(p["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(p["nombre"])}</a>',
                  '<span class="discount">' + f'{p["descuento"]:g}'.replace('.', ',') + ' %</span>',
                  euro(p['precio_centimos']), esc(p['consola']), euro(p['referencia_centimos']),
                  euro(p['bajada_centimos']), esc(p['formato']),
                  esc(p['disponibilidad']), esc(p['vendedor'])]
        rows.append(f'<tr data-discount="{float(p["descuento"])}" data-price="{int(p["precio_centimos"])}">' + ''.join('<td>'+f+'</td>' for f in fields) + '</tr>')
    status = 'Recorrido completo' if not warnings else 'Recorrido parcial: ' + '; '.join(warnings)
    target.write_text('''<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Ofertas Switch · MediaMarkt</title>
<style>body{font:16px system-ui;background:#f4f5f8;color:#19202c;margin:0;padding:32px}main{max-width:1500px;margin:auto}h1{letter-spacing:-1px}input,select{padding:12px;border:1px solid #ccd;border-radius:8px;margin:6px}table{border-collapse:collapse;width:100%;background:white}td,th{padding:14px;text-align:left;border-bottom:1px solid #eee}a{color:#b00020}th{background:#19202c;color:white}small{color:#565b65}.scroll{overflow:auto}#count{font-weight:bold;margin:16px 0}.discount{display:inline-block;color:#09613e;background:#e3f6eb;padding:7px 10px;border-radius:7px;font-size:18px;font-weight:800;white-space:nowrap}#sort-discount{color:inherit;background:transparent;border:0;font:inherit;font-weight:700;padding:6px 0;cursor:pointer;white-space:nowrap}#sort-discount:focus-visible{outline:2px solid white;outline-offset:3px}td:first-child{min-width:160px;max-width:260px}td:nth-child(3){white-space:nowrap}@media(max-width:600px){body{padding:16px}td,th{padding:12px 8px}td:first-child{min-width:140px;max-width:160px}.discount{font-size:17px;padding:7px}h1{font-size:26px}}</style>
<main><h1>Ofertas de Switch y Switch 2</h1><p>MediaMarkt España · ''' + esc(stamp) + '''</p><p style="padding:14px;background:#fff0ca;border-radius:8px">''' + esc(status) + '''</p>
<small>Precio del juego, sin gastos de envío. Referencia = precio tachado de la tienda, no mínimo histórico.
La bajada compara con tu ejecución anterior. «No especificado» no garantiza cartucho completo ni vendedor MediaMarkt.</small>
<p><input id="q" placeholder="Buscar juego" aria-label="Buscar juego"><select id="platform" aria-label="Consola"><option value="">Ambas consolas</option><option>Switch</option><option>Switch 2</option></select>
<input id="max" type="number" min="0" placeholder="Precio máximo €" aria-label="Precio máximo">
<label><input id="offers" type="checkbox" checked>Solo descuentos o bajadas</label></p>
<p><label for="sort">Ordenar por:</label><select id="sort" aria-label="Ordenar por"><option value="discount-desc">Mayor % de descuento primero</option><option value="discount-asc">Menor % de descuento primero</option></select></p><div id="count" aria-live="polite"></div>
<div class="scroll"><table><thead><tr><th scope="col">Juego</th><th id="discount-heading" scope="col" aria-sort="descending"><button id="sort-discount" type="button" aria-label="Ordenar por porcentaje de descuento, de menor a mayor">% descuento <span id="sort-arrow" aria-hidden="true">↓</span></button></th>''' + ''.join('<th scope="col">'+s+'</th>' for s in ['Precio','Consola','Referencia','Bajada','Formato','Disponibilidad','Vendedor']) + '''</tr></thead><tbody>''' + ''.join(rows) + '''</tbody></table></div>
<script>
const $=id=>document.getElementById(id);
const tbody=document.querySelector('tbody');
const rows=Array.from(tbody.rows);
function update(){
  const ascending=$('sort').value==='discount-asc';
  rows.sort((a,b)=>(ascending?1:-1)*(Number(a.dataset.discount)-Number(b.dataset.discount))||Number(a.dataset.price)-Number(b.dataset.price)||a.cells[0].textContent.localeCompare(b.cells[0].textContent,'es'));
  tbody.append(...rows);
  $('discount-heading').setAttribute('aria-sort',ascending?'ascending':'descending');
  $('sort-arrow').textContent=ascending?'↑':'↓';
  $('sort-discount').setAttribute('aria-label','Ordenar por porcentaje de descuento, '+(ascending?'de mayor a menor':'de menor a mayor'));
  let n=0;
  rows.forEach(r=>{
    const c=r.cells;
    const drop=parseFloat(c[5].textContent.replace(',','.'))||0;
    const show=c[0].textContent.toLowerCase().includes($('q').value.toLowerCase())&&(!$('platform').value||c[3].textContent===$('platform').value)&&(!$('max').value||Number(r.dataset.price)<=Number($('max').value)*100)&&(!$('offers').checked||Number(r.dataset.discount)>0||drop>0);
    r.hidden=!show;if(show)n++;
  });
  $('count').textContent=n+' juegos';
}
document.querySelectorAll('input,select').forEach(e=>e.addEventListener('input',update));
$('sort-discount').addEventListener('click',()=>{$('sort').value=$('sort').value==='discount-desc'?'discount-asc':'discount-desc';update()});
update();
</script></main></html>''', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--consola', choices=['ambas','switch','switch2'], default='ambas')
    ap.add_argument('--max-paginas', type=int, default=200, help='Límite por consola; si se alcanza, se marca parcial')
    ap.add_argument('--pausa', type=float, default=3, help='Segundos entre peticiones (mínimo 2)')
    ap.add_argument('--precio-max', type=float)
    ap.add_argument('--descuento-min', type=float, default=0)
    ap.add_argument('--solo-ofertas', action='store_true')
    ap.add_argument('--solo-disponibles', action='store_true')
    ap.add_argument('--salida', type=Path, default=Path('resultados'))
    args = ap.parse_args()
    if args.max_paginas < 1 or args.pausa < 2:
        ap.error('Usa --max-paginas >= 1 y --pausa >= 2')
    args.salida.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    products, warnings, seen = {}, [], set()
    rp = robots()
    pause = max(args.pausa, rp.crawl_delay(AGENT) or rp.crawl_delay('*') or 0)
    sources = SOURCES if args.consola == 'ambas' else {('Switch' if args.consola == 'switch' else 'Switch 2'): SOURCES['Switch' if args.consola == 'switch' else 'Switch 2']}
    for platform, url in sources.items():
        for page in range(1, args.max_paginas+1):
            if not url:
                break
            if url in seen:
                warnings.append(f'{platform}: paginación repetida'); break
            if not rp.can_fetch(AGENT, url):
                warnings.append(f'{platform}: robots.txt no permite {url}'); break
            seen.add(url)
            time.sleep(pause)
            print(f'{platform}: página {page}', file=sys.stderr)
            try:
                source = fetch(url)
                batch, next_url = parse(source, platform)
                if not batch:
                    raise ValueError('Sin fichas reconocibles: posible bloqueo o cambio de HTML')
                fresh = [p for p in batch if p['url'] not in products]
                if not fresh:
                    raise ValueError('La página repite productos; recorrido detenido')
                products.update((p['url'], p) for p in batch)
                site_paging = paging(source)
                if site_paging:
                    current, count, size, maximum = site_paging
                    if current >= maximum and count > maximum:
                        warnings.append(f'{platform}: límite de paginación de MediaMarkt (primeras {maximum} de {count} páginas; hasta {maximum*size} fichas)')
                        url = None
                        break
                url = next_url
            except (HTTPError, URLError, TimeoutError, ValueError) as e:
                warnings.append(f'{platform}: {e}'); break
        else:
            if url:
                warnings.append(f'{platform}: límite de {args.max_paginas} páginas alcanzado')
    if not products:
        raise ValueError('No se han obtenido productos. ' + '; '.join(warnings))
    all_products = list(products.values())
    history(all_products, args.salida/'historial.sqlite', stamp)
    selected = [p for p in all_products
        if (args.precio_max is None or p['precio_centimos'] <= round(args.precio_max*100))
        and p['descuento'] >= args.descuento_min
        and (not args.solo_disponibles or p['disponible_online'])
        and (not args.solo_ofertas or p['descuento'] > 0 or p['bajada_centimos'] > 0)]
    selected.sort(key=lambda p: (-p['descuento'], p['precio_centimos']))
    (args.salida/'productos.json').write_text(json.dumps(dict(fecha=stamp, avisos=warnings,
        total_observado=len(all_products), productos=selected), ensure_ascii=False, indent=2), encoding='utf-8')
    with (args.salida/'productos.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(all_products[0]), delimiter=';')
        writer.writeheader(); writer.writerows(selected)
    report(selected, args.salida/'ofertas.html', stamp, warnings)
    print(f'{len(all_products)} observados; {len(selected)} seleccionados. Abre {args.salida / "ofertas.html"}')
    for warning in warnings:
        print('AVISO: '+warning, file=sys.stderr)
    return 2 if warnings else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (HTTPError, URLError, TimeoutError, ValueError, sqlite3.Error, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
