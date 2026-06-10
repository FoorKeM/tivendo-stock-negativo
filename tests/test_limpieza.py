import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import flujo_ajuste


class DownloadCleanupTests(unittest.TestCase):
    def test_elimina_archivos_y_registra_resultado(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            download_dir = directory / "descargas"
            download_dir.mkdir()
            (download_dir / "inventario.xlsx").write_bytes(b"xlsx")
            (download_dir / "articulos.xlsx").write_bytes(b"xlsx")
            result = directory / "resultado.json"
            result.write_text('{"estado": "guardado"}', encoding="utf-8")

            with patch.object(flujo_ajuste, "DOWNLOAD_DIR", download_dir):
                deleted = flujo_ajuste.limpiar_descargas(result)

            payload = json.loads(result.read_text(encoding="utf-8"))
            self.assertEqual(len(deleted), 2)
            self.assertEqual(list(download_dir.iterdir()), [])
            self.assertEqual(
                len(payload["limpieza_descargas"]["archivos_eliminados"]),
                2,
            )
            self.assertEqual(payload["limpieza_descargas"]["errores"], [])


if __name__ == "__main__":
    unittest.main()
