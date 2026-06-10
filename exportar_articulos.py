from datetime import datetime
from pathlib import Path

from app_paths import DOWNLOAD_DIR
from exportar_inventario import log


ARTICLES_URL = "https://tivendoapp.defontana.com/articulos/listado_articulos"


async def exportar_listado_articulos(page) -> Path:
    log("Abriendo Listado de articulos...")
    await page.goto(ARTICLES_URL, timeout=45000)
    button = page.get_by_role("button", name="Exportar")
    await button.wait_for(state="visible", timeout=30000)
    log("Exportando listado de articulos...")
    async with page.expect_download(timeout=300000) as info:
        await button.click()
    download = await info.value
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = DOWNLOAD_DIR / f"Listado_Articulos_{stamp}.xlsx"
    await download.save_as(str(destination))
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("El listado de articulos descargado esta vacio.")
    log(f"Listado de articulos descargado: {destination}")
    return destination
