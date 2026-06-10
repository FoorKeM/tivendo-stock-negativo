import asyncio
import json
import re
from datetime import datetime
from pathlib import Path

from app_paths import DIAG_DIR, DOWNLOAD_DIR, configure_playwright_browsers

configure_playwright_browsers()

from playwright.async_api import async_playwright


LOGIN_URL = "https://tivendoapp.defontana.com/login"
WAREHOUSE = "LIBERTADOR 1476"


def log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with (DIAG_DIR.parent / "exportacion.log").open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


async def _launch_browser(playwright, visible: bool):
    last_error = None
    for channel in ("msedge", "chrome", None):
        try:
            kwargs = {"headless": not visible}
            if channel:
                kwargs["channel"] = channel
            return await playwright.chromium.launch(**kwargs)
        except Exception as exc:
            last_error = exc
    raise RuntimeError("No se pudo abrir Edge, Chrome ni Chromium.") from last_error


async def _save_diagnostic(page, error: Exception) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = DIAG_DIR / f"{stamp}_exportacion"
    data = {"fecha": stamp, "error": str(error), "url": "", "titulo": ""}
    try:
        data["url"] = page.url
        data["titulo"] = await page.title()
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
    except Exception:
        pass
    base.with_suffix(".json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def _login(page, email: str, password: str) -> None:
    log("Abriendo Tivendo...")
    await page.goto(LOGIN_URL, timeout=45000)
    await page.wait_for_load_state("domcontentloaded")

    try:
        await page.locator("input").first.wait_for(state="visible", timeout=30000)
    except Exception:
        if "login" not in page.url.lower():
            log("Sesion de Tivendo reutilizada.")
            return
        raise RuntimeError(
            "Tivendo no termino de mostrar el formulario de acceso despues de 30 segundos."
        )

    inputs = page.locator("input")
    if await inputs.count() < 2:
        raise RuntimeError("Tivendo mostro un formulario de acceso incompleto.")
    await inputs.nth(0).fill(email)
    await inputs.nth(1).fill(password)
    button = page.get_by_role(
        "button",
        name=re.compile(r"Iniciar Sesi.n", re.IGNORECASE),
    )
    await button.wait_for(state="visible", timeout=10000)
    await button.click()
    try:
        await page.wait_for_url(lambda url: "login" not in url.lower(), timeout=30000)
    except Exception:
        pass
    if "login" in page.url.lower():
        raise RuntimeError(
            "Tivendo no acepto el acceso. Abre el EXE y usa "
            "'Editar credenciales'."
        )
    log("Ingreso a Tivendo completado.")


async def _select_company(page) -> None:
    body = (await page.locator("body").inner_text()).upper()
    if "MERCADO HOUSE SPA" in body:
        return

    current = page.get_by_text("NO USAR", exact=False)
    if await current.count() == 0:
        log("No se pudo leer la empresa activa; se continua con la sesion actual.")
        return
    await current.first.click()
    option = page.get_by_text("MERCADO HOUSE SPA", exact=True)
    await option.wait_for(state="visible", timeout=15000)
    await option.click()
    await page.wait_for_timeout(1500)
    log("Empresa MERCADO HOUSE SPA seleccionada.")


async def _open_pos(context, page):
    card = page.get_by_text("Punto de Ventas", exact=False)
    await card.first.wait_for(state="visible", timeout=20000)
    try:
        async with context.expect_page(timeout=4000) as info:
            await card.first.click()
        pos = await info.value
    except Exception:
        pos = page
    await pos.wait_for_load_state("domcontentloaded")
    await pos.get_by_text("Informes", exact=True).first.wait_for(state="visible", timeout=30000)
    log("Punto de Ventas abierto.")
    return pos


async def _open_inventory_report(page) -> None:
    reports = page.get_by_text("Informes", exact=True)
    await reports.first.click()
    inventory = page.get_by_text("Informes de Inventario", exact=True)
    await inventory.wait_for(state="visible", timeout=15000)
    await inventory.click()
    await page.get_by_text("Bodegas", exact=True).wait_for(state="visible", timeout=30000)
    menu_toggle = page.locator("#menu_lateral button.boton_toggle_menu")
    if await menu_toggle.count():
        await menu_toggle.evaluate("element => element.click()")
        await page.wait_for_timeout(500)
    log("Informe de Inventario abierto.")


async def _select_single_warehouse(page) -> None:
    selector = page.locator(
        '[role="combobox"][aria-labelledby*="selector_tipo_consulta_bodegas"]'
    )
    await selector.wait_for(state="visible", timeout=10000)
    await selector.click()
    option = page.get_by_role(
        "option",
        name=re.compile(r"Una en Particular", re.IGNORECASE),
    )
    await option.wait_for(state="visible", timeout=10000)
    await option.click()


async def _choose_warehouse(page) -> None:
    await _select_single_warehouse(page)
    await page.wait_for_timeout(400)

    search = page.locator(
        'input[type="text"]:not(.MuiSelect-nativeInput)'
    ).first
    await search.wait_for(state="visible", timeout=10000)
    await search.fill("lib")
    option = page.get_by_text(WAREHOUSE, exact=True)
    await option.wait_for(state="visible", timeout=15000)
    await option.click()
    log(f"Bodega seleccionada: {WAREHOUSE}.")


async def _enable_out_of_stock(page) -> None:
    checkbox = page.locator(
        'input[name="informes_de_ventas_muestra_articulos_sin_stock"]'
    )
    await checkbox.wait_for(state="attached", timeout=10000)
    if not await checkbox.is_checked():
        await checkbox.check()
    log("Opcion 'Muestra articulos sin stock' activada.")


async def _ensure_summary(page) -> None:
    summary = page.locator(
        'input[name="radios_nivel_de_presentacion_informes_de_inventario"]'
        '[value="Resumido"]'
    )
    await summary.wait_for(state="attached", timeout=10000)
    if not await summary.is_checked():
        await summary.check()
    log("Presentacion 'Resumido' confirmada.")


async def _export(page) -> Path:
    button = page.get_by_role("button", name="Exportar")
    await button.wait_for(state="visible", timeout=15000)
    log("Exportando informe...")
    async with page.expect_download(timeout=300000) as info:
        await button.click()
    download = await info.value
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = Path(download.suggested_filename or "inventario.xlsx").suffix or ".xlsx"
    destination = DOWNLOAD_DIR / f"Inventario_Libertador_{stamp}{suffix}"
    await download.save_as(str(destination))
    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("La descarga termino, pero el archivo esta vacio o no existe.")
    log(f"Informe descargado: {destination}")
    return destination


async def exportar(email: str, password: str, visible: bool = True) -> Path:
    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright, visible)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()
        active_page = page
        try:
            await _login(page, email, password)
            await _select_company(page)
            active_page = await _open_pos(context, page)
            await _open_inventory_report(active_page)
            await _choose_warehouse(active_page)
            await _enable_out_of_stock(active_page)
            await _ensure_summary(active_page)
            result = await _export(active_page)
            return result
        except Exception as exc:
            await _save_diagnostic(active_page, exc)
            raise
        finally:
            await browser.close()
