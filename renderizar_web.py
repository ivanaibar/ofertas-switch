"""Regenera la presentación con la última consulta, conservando su fecha."""
import csv
import json
from pathlib import Path
from urllib.request import urlopen
from scraper import report

snapshot = Path('data/productos.json')
if snapshot.exists():
    data = json.loads(snapshot.read_text(encoding='utf-8'))
else:
    with urlopen('https://ivanaibar.github.io/ofertas-switch/productos.json', timeout=30) as response:
        data = json.load(response)
products = data['productos']
if not products:
    raise ValueError('La última consulta no contiene productos')
output = Path('resultados')
output.mkdir(exist_ok=True)
(output/'productos.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
with (output/'productos.csv').open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f,fieldnames=list(products[0]),delimiter=';')
    writer.writeheader();writer.writerows(products)
report(products, output/'ofertas.html', data['fecha'], data.get('avisos',[]))
