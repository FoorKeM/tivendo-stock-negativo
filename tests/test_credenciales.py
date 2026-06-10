import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import credenciales


class CredentialTests(unittest.TestCase):
    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "credenciales.json"
            with patch.object(credenciales, "CRED_FILE", target):
                credenciales.guardar("usuario@example.com", "secreto")
                result = credenciales.cargar()

        self.assertEqual(result["email"], "usuario@example.com")
        self.assertEqual(result["password"], "secreto")

    def test_cargar_devuelve_vacio_si_no_hay_archivo_propio(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "credenciales.json"
            with patch.object(credenciales, "CRED_FILE", target):
                result = credenciales.cargar()

            self.assertEqual(result, {})
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
