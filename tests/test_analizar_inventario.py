import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from analizar_inventario import cruzar_negativos, leer_negativos


def crear_libro(path: Path, rows: list[list]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    workbook.save(path)


class InventoryAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.inventory = self.directory / "inventario.xlsx"
        self.articles = self.directory / "articulos.xlsx"

    def tearDown(self):
        self.temp.cleanup()

    def test_solo_incluye_codigos_a_con_cantidad_negativa(self):
        crear_libro(
            self.inventory,
            [
                ["titulo"],
                ["CodArticulo", "Descripción Artículo", "Cantidad"],
                ["A1", "Negativo", -15],
                ["A2", "Cero", 0],
                ["A3", "Positivo", 4],
                ["P1", "Pack negativo", -8],
            ],
        )

        result = leer_negativos(self.inventory)

        self.assertEqual([item["codigo"] for item in result], ["A1"])
        self.assertEqual(str(result[0]["stock"]), "-15")

    def test_cruce_preserva_barcode_y_decimales(self):
        crear_libro(
            self.inventory,
            [
                ["CodArticulo", "Descripción Artículo", "Cantidad"],
                ["A1", "Producto", -0.264],
            ],
        )
        crear_libro(
            self.articles,
            [
                [
                    "Código",
                    "Nombre",
                    "Código barra interno",
                    "Disponible para venta",
                    "Activo",
                ],
                ["A1", "Producto", "0000123", "Si", "Si"],
            ],
        )

        result = cruzar_negativos(self.inventory, self.articles)

        self.assertEqual(result[0].codigo_barra, "0000123")
        self.assertEqual(result[0].cantidad_propuesta, "0.264")

    def test_aborta_si_el_articulo_esta_duplicado(self):
        crear_libro(
            self.inventory,
            [
                ["CodArticulo", "Descripción Artículo", "Cantidad"],
                ["A1", "Producto", -2],
            ],
        )
        crear_libro(
            self.articles,
            [
                [
                    "Código",
                    "Nombre",
                    "Código barra interno",
                    "Disponible para venta",
                    "Activo",
                ],
                ["A1", "Producto", "123", "Si", "Si"],
                ["A1", "Producto repetido", "456", "Si", "Si"],
            ],
        )

        with self.assertRaisesRegex(ValueError, "hay 2"):
            cruzar_negativos(self.inventory, self.articles)

    def test_aborta_si_no_hay_codigo_barra(self):
        crear_libro(
            self.inventory,
            [
                ["CodArticulo", "Descripción Artículo", "Cantidad"],
                ["A1", "Producto", -2],
            ],
        )
        crear_libro(
            self.articles,
            [
                [
                    "Código",
                    "Nombre",
                    "Código barra interno",
                    "Disponible para venta",
                    "Activo",
                ],
                ["A1", "Producto", "", "Si", "Si"],
            ],
        )

        with self.assertRaisesRegex(ValueError, "sin Codigo barra interno"):
            cruzar_negativos(self.inventory, self.articles)

    def test_aborta_si_el_articulo_esta_inactivo(self):
        crear_libro(
            self.inventory,
            [
                ["CodArticulo", "Descripción Artículo", "Cantidad"],
                ["A1", "Producto", -2],
            ],
        )
        crear_libro(
            self.articles,
            [
                [
                    "Código",
                    "Nombre",
                    "Código barra interno",
                    "Disponible para venta",
                    "Activo",
                ],
                ["A1", "Producto", "123", "Si", "No"],
            ],
        )

        with self.assertRaisesRegex(ValueError, "articulo inactivo"):
            cruzar_negativos(self.inventory, self.articles)


if __name__ == "__main__":
    unittest.main()
