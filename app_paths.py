import os
import sys
from pathlib import Path


IS_FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).resolve().parent if IS_FROZEN else Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("LOCALAPPDATA", APP_DIR)) / "TivendoStockNegativo"
DOWNLOAD_DIR = DATA_DIR / "descargas"
DIAG_DIR = DATA_DIR / "diagnosticos"
ADJUSTMENT_DIR = DATA_DIR / "ajustes"

for directory in (DATA_DIR, DOWNLOAD_DIR, DIAG_DIR, ADJUSTMENT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def configure_playwright_browsers() -> None:
    portable = APP_DIR / "ms-playwright"
    if portable.exists():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(portable))
