import json
import tempfile
import unittest
from pathlib import Path
from preparar_web import prepare


class PublicationTests(unittest.TestCase):
    def test_partial_does_not_replace_site(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'resultados'; source.mkdir()
            target=root/'public'; target.mkdir()
            (target/'index.html').write_text('anterior')
            (source/'productos.json').write_text(json.dumps({'avisos':['parcial'],'productos':[{}]}))
            with self.assertRaises(ValueError): prepare(source,target)
            self.assertEqual((target/'index.html').read_text(),'anterior')

    def test_only_public_files_exported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'resultados'; source.mkdir(); target=root/'public'
            (source/'productos.json').write_text(json.dumps({'avisos':[],'productos':[{}]}))
            (source/'ofertas.html').write_text('informe')
            (source/'productos.csv').write_text('csv')
            (source/'historial.sqlite').write_text('privado del runtime')
            prepare(source,target)
            self.assertEqual({p.name for p in target.iterdir()}, {'index.html','productos.csv','productos.json'})

    def test_catalog_limit_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); source=root/'resultados'; source.mkdir(); target=root/'public'
            data={'avisos':['Switch: límite de paginación de MediaMarkt (30 páginas)'],'productos':[{}]}
            (source/'productos.json').write_text(json.dumps(data))
            (source/'ofertas.html').write_text('Aviso de catálogo parcial')
            (source/'productos.csv').write_text('csv')
            with self.assertRaises(ValueError): prepare(source,target)
            prepare(source,target,True)
            data['avisos'].append('Switch: HTTP Error 403')
            (source/'productos.json').write_text(json.dumps(data))
            with self.assertRaises(ValueError): prepare(source,target,True)


if __name__ == '__main__': unittest.main()
