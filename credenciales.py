import json

from app_paths import DATA_DIR


CRED_FILE = DATA_DIR / "credenciales.json"


def cargar() -> dict:
    if CRED_FILE.exists():
        try:
            data = json.loads(CRED_FILE.read_text(encoding="utf-8"))
            if data.get("email") and data.get("password"):
                return data
        except Exception:
            pass

    return {}


def guardar(email: str, password: str) -> None:
    CRED_FILE.write_text(
        json.dumps({"email": email.strip(), "password": password}, indent=2),
        encoding="utf-8",
    )
