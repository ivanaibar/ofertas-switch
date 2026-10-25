import tempfile
import unittest
from pathlib import Path
from scraper import amounts, history, parse, report


class ScraperTests(unittest.TestCase):
    def test_spanish_prices(self):
        self.assertEqual(amounts('25,– € 1.299,99 € -15% 4.8'), [2500, 129999])

    def test_price_scope_and_pagination(self):
        source = '''<link rel="next" href="/es/category/juegos-nintendo-switch-2-8550.html?page=2">
        <article data-test="mms-product-card"><a data-test="mms-router-link-product-list-item-link" href="/es/product/_test-123.html"><h3 data-test="product-title">Nintendo Switch 2 Test (Game Key Card)</h3></a>
        <div data-test="cofr-price product-price"><div data-test="mms-price"><div data-test="mms-strike-price-type-flp">59,99 € 59,99€</div>29,99 € 29,99€</div></div>
        <div>Reacondicionado desde 15,00 €</div><div data-test="product-delivery"><div data-test="mms-cofr-delivery_AVAILABLE">Disponible online</div></div></article>'''
        rows, nxt = parse(source, 'Switch 2')
        p = rows[0]
        self.assertEqual(p['precio_centimos'], 2999)
        self.assertEqual(p['referencia_centimos'], 5999)
        self.assertTrue(p['disponible_online'])
        self.assertEqual(p['formato'], 'Game Key Card')
        self.assertTrue(nxt.endswith('?page=2'))
        unavailable, _ = parse(source.replace('mms-cofr-delivery_AVAILABLE','mms-cofr-delivery_UNAVAILABLE'), 'Switch 2')
        self.assertFalse(unavailable[0]['disponible_online'])

    def test_history_compares_previous_not_reference(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'prices.sqlite'
            products = [dict(url='u', precio_centimos=4000)]
            history(products,path,'2026-01-01')
            self.assertEqual(products[0]['bajada_centimos'], 0)
            products[0]['precio_centimos'] = 3000
            history(products,path,'2026-01-02')
            self.assertEqual(products[0]['bajada_centimos'], 1000)
            products[0]['precio_centimos'] = 3500
            history(products,path,'2026-01-03')
            self.assertEqual(products[0]['bajada_centimos'], 0)
            self.assertEqual(products[0]['minimo_observado_centimos'], 3000)


if __name__ == '__main__':
    unittest.main()
