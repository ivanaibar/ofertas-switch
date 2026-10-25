"""Publica solo HTML, CSV y JSON, sin exponer la base de datos."""
import argparse
import json
import shutil
from pathlib import Path


def prepare(source, target):
    data = json.loads((source/'productos.json').read_text(encoding='utf-8'))
    if data.get('avisos') or not data.get('productos'):
        raise ValueError('No se publica una consulta parcial o vacía')
    # Verifica las entradas antes de sustituir cualquier fichero.
    files = [('ofertas.html','index.html'), ('productos.json','productos.json'),
             ('productos.csv','productos.csv')]
    for origin, _ in files:
        if not (source/origin).is_file():
            raise ValueError(f'Falta {origin}')
    target.mkdir(parents=True, exist_ok=True)
    for origin, dest in files:
        shutil.copyfile(source/origin, target/dest)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--origen',type=Path,default=Path('resultados'))
    ap.add_argument('--destino',type=Path,default=Path('public'))
    args = ap.parse_args()
    prepare(args.origen,args.destino)
