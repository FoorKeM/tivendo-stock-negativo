import json
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from playwright.async_api import async_playwright

from analizar_inventario import (
    AdjustmentItem,
    cruzar_negativos,
    guardar_propuesta,
    leer_negativos,
)
from app_paths import ADJUSTMENT_DIR, DOWNLOAD_DIR
from exportar_articulos import exportar_listado_articulos
from exportar_inventario import (
    _choose_warehouse,
    _enable_out_of_stock,
    _ensure_summary,
    _export,
    _launch_browser,
    _login,
    _open_inventory_report,
    _open_pos,
    _save_diagnostic,
    _select_company,
    log,
)


async def preparar(email: str, password: str, visible: bool = True):
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
            inventory_path = await _export(active_page)

            articles_path = await exportar_listado_articulos(active_page)
            items = cruzar_negativos(inventory_path, articles_path)
            proposal_path = guardar_propuesta(inventory_path, articles_path, items)
            log(f"Propuesta creada con {len(items)} articulos: {proposal_path}")
            return inventory_path, articles_path, proposal_path, items
        except Exception as exc:
            await _save_diagnostic(active_page, exc)
            raise
        finally:
            await browser.close()


async def _select_option(page, selector: str, option: str) -> None:
    control = page.locator(selector)
    await control.wait_for(state="visible", timeout=30000)
    await control.click()
    target = page.get_by_role("option", name=option, exact=True)
    await target.wait_for(state="visible", timeout=15000)
    await target.click()


async def _open_movement(page) -> None:
    inventory = page.get_by_text("Inventario", exact=True).first
    await inventory.wait_for(state="visible", timeout=30000)
    await inventory.click()
    movement = page.get_by_text("Nuevo movimiento", exact=True)
    await movement.wait_for(state="visible", timeout=15000)
    await movement.click()
    await page.locator("#selector_selector_documento_inventario").wait_for(
        state="visible",
        timeout=30000,
    )
    toggle = page.locator("#menu_lateral button.boton_toggle_menu")
    if await toggle.count():
        await toggle.evaluate("element => element.click()")
        await page.wait_for_timeout(500)


async def _configure_movement(page) -> None:
    await _select_option(
        page,
        "#selector_selector_documento_inventario",
        "AJUSTE POSITIVO DE INVENTARIO",
    )
    await _select_option(
        page,
        "#selector_selector_motivo_movimiento_inventario",
        "ENTRADA",
    )
    await _select_option(
        page,
        '[id*="inventario_bodega_"][role="combobox"]',
        "LIBERTADOR 1476",
    )
    textarea = page.locator("textarea").first
    await textarea.fill(
        f"Regularizacion stock negativo LIBERTADOR 1476 - "
        f"{datetime.now():%Y-%m-%d}"
    )


async def _wait_catalog(page) -> None:
    search = page.locator('input[placeholder*="digo o nombre"]')
    await search.wait_for(state="visible", timeout=30000)
    indicator = page.get_by_role("button", name="Tivendo SOS", exact=False)
    if await indicator.count():
        started = time.monotonic()
        log("Esperando que Tivendo prepare el catalogo de articulos...")
        try:
            next_message = 10
            while True:
                optimizing = await page.evaluate(
                    """
                    () => {
                        const button = [...document.querySelectorAll('button')]
                            .find(el => (el.getAttribute('aria-label') || '')
                                .includes('Tivendo SOS'));
                        if (!button) return false;
                        return /Optimizando/i.test(
                            button.getAttribute('aria-label') || ''
                        );
                    }
                    """
                )
                if not optimizing:
                    break
                elapsed = int(time.monotonic() - started)
                if elapsed >= 180:
                    raise TimeoutError
                if elapsed >= next_message:
                    log(f"Tivendo sigue preparando el catalogo ({elapsed} s)...")
                    next_message += 10
                await page.wait_for_timeout(2000)
        except Exception:
            log("Tivendo sigue optimizando; se intentara usar el buscador.")
        else:
            elapsed = int(time.monotonic() - started)
            log(f"Catalogo de Tivendo listo ({elapsed} s).")


async def _search_product(page, item: AdjustmentItem):
    blank_row = page.locator("tr.articulos_inventario_tr").filter(
        has=page.locator("td.sin_seleccionar_articulo")
    ).last
    search = blank_row.locator('input[placeholder*="digo o nombre"]')
    await search.wait_for(state="visible", timeout=30000)

    async with page.expect_response(
        lambda response: "/producto/paginado" in response.url,
        timeout=120000,
    ) as response_info:
        await search.fill(item.codigo)
    response = await response_info.value
    payload = await response.json()
    products = payload.get("productos") or []
    matches = [product for product in products if product.get("sku") == item.codigo]
    if len(matches) != 1:
        raise RuntimeError(
            f"Tivendo devolvio {len(matches)} coincidencias para {item.codigo}."
        )

    product = matches[0]
    if str(product.get("codigoInterno") or "") != item.codigo_barra:
        raise RuntimeError(
            f"El codigo de barra de {item.codigo} cambio en Tivendo: "
            f"{product.get('codigoInterno')!r}."
        )
    if str(product.get("nombre") or "").strip() != item.descripcion:
        raise RuntimeError(
            f"El nombre de {item.codigo} no coincide con el informe."
        )

    warehouse_stock = None
    stock_data = product.get("stock") or {}
    for warehouse in stock_data.get("bodegasConStock") or []:
        if warehouse.get("idBodega") == "LAS COMPAÑIAS":
            warehouse_stock = warehouse.get("stock")
            break
    if warehouse_stock is None:
        raise RuntimeError(
            f"Tivendo no devolvio stock de LIBERTADOR 1476 para {item.codigo}."
        )
    stock = _parse_stock(str(warehouse_stock))
    if stock >= 0:
        await search.fill("")
        return None, stock

    code = page.locator(
        f'li[role="menuitem"] h6.codigo_articulo[aria-label="{item.codigo}"]'
    )
    await code.wait_for(state="visible", timeout=15000)
    enabled_quantities = page.locator('input[type="number"]:not([disabled])')
    previous_count = await enabled_quantities.count()
    await code.click()
    await page.wait_for_function(
        """
        expected => document.querySelectorAll(
            'input[type="number"]:not([disabled])'
        ).length > expected
        """,
        arg=previous_count,
        timeout=15000,
    )

    selected_rows = page.locator("tr.articulos_inventario_tr").filter(
        has=page.locator('input[type="number"]:not([disabled])')
    )
    await selected_rows.first.wait_for(state="visible", timeout=15000)
    placeholders = []
    for index in range(await selected_rows.count()):
        candidate = selected_rows.nth(index)
        product_input = candidate.locator('input[type="text"]').first
        placeholder = await product_input.get_attribute("placeholder") or ""
        placeholders.append(placeholder)
        if placeholder == item.descripcion:
            return candidate, stock
    raise RuntimeError(
        f"No se encontro la fila seleccionada de {item.codigo} despues de agregarla. "
        f"Filas visibles: {placeholders!r}"
    )


def _parse_stock(value: str):
    normalized = value.strip().replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise RuntimeError(f"No se pudo leer el stock actual: {value!r}") from exc


async def _load_item(page, item: AdjustmentItem) -> dict:
    row, api_stock = await _search_product(page, item)
    if row is None:
        return {
            "codigo": item.codigo,
            "codigo_barra": item.codigo_barra,
            "stock_actual": format(api_stock, "f"),
            "estado": "omitido_no_negativo",
        }

    stock_display = row.locator(".informacion_stock_articulo")
    stock_text = await stock_display.get_attribute("aria-label") or ""
    displayed_stock = _parse_stock(stock_text)
    if displayed_stock != api_stock:
        raise RuntimeError(
            f"El stock mostrado de {item.codigo} ({displayed_stock}) no coincide "
            f"con la API ({api_stock})."
        )
    if displayed_stock >= 0:
        raise RuntimeError(
            f"{item.codigo} dejo de estar negativo durante la seleccion."
        )

    quantity_input = row.locator('input[type="number"]:not([disabled])')
    quantity = format(abs(displayed_stock), "f")
    await quantity_input.fill(quantity)
    return {
        "codigo": item.codigo,
        "codigo_barra": item.codigo_barra,
        "stock_actual": stock_text,
        "cantidad": quantity,
        "estado": "cargado",
    }


def _save_result(payload: dict) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ADJUSTMENT_DIR / f"resultado_ajuste_{stamp}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def anexar_verificacion(result_path: Path, inventory_path: Path) -> None:
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    remaining = leer_negativos(inventory_path)
    payload["verificacion"] = {
        "inventario_posterior": str(inventory_path),
        "negativos_a_restantes": len(remaining),
        "codigos_restantes": [item["codigo"] for item in remaining],
    }
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def limpiar_descargas(result_path: Path) -> list[str]:
    deleted = []
    errors = []
    for path in DOWNLOAD_DIR.iterdir():
        if not path.is_file():
            continue
        try:
            path.unlink()
            deleted.append(str(path))
        except OSError as exc:
            errors.append(f"{path}: {exc}")

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["limpieza_descargas"] = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "archivos_eliminados": deleted,
        "errores": errors,
    }
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if errors:
        raise RuntimeError(
            "El ajuste se completo, pero no se pudieron eliminar todas las "
            "descargas:\n- " + "\n- ".join(errors)
        )
    return deleted


async def aplicar(
    email: str,
    password: str,
    items: list[AdjustmentItem],
    visible: bool = True,
    simulate: bool = False,
) -> Path:
    async with async_playwright() as playwright:
        browser = await _launch_browser(playwright, visible)
        context = await browser.new_context()
        page = await context.new_page()
        active_page = page
        results = []
        try:
            await _login(page, email, password)
            await _select_company(page)
            active_page = await _open_pos(context, page)
            log("Abriendo Nuevo movimiento...")
            await _open_movement(active_page)
            log("Configurando ajuste positivo, entrada y bodega...")
            await _configure_movement(active_page)
            log("Movimiento configurado.")
            await _wait_catalog(active_page)

            for index, item in enumerate(items, start=1):
                log(f"Validando articulo {index}/{len(items)}: {item.codigo}")
                results.append(await _load_item(active_page, item))

            loaded = [item for item in results if item["estado"] == "cargado"]
            if not loaded:
                raise RuntimeError("No quedan articulos con stock actual negativo.")

            payload = {
                "fecha": datetime.now().isoformat(timespec="seconds"),
                "simulacion": simulate,
                "bodega": "LIBERTADOR 1476",
                "articulos": results,
            }
            if simulate:
                payload["estado"] = "simulado_sin_guardar"
                await active_page.screenshot(
                    path=str(ADJUSTMENT_DIR / "ultima_simulacion.png"),
                    full_page=True,
                )
            else:
                payload["estado"] = "guardado_pendiente_confirmacion"
                payload["guardar_iniciado"] = datetime.now().isoformat(
                    timespec="seconds"
                )
                result_path = _save_result(payload)
                button = active_page.get_by_role("button", name="Guardar", exact=True)
                responses = []

                def record_response(response):
                    if (
                        response.request.method in {"POST", "PUT"}
                        and "api-pos-prod.defontana.com" in response.url
                    ):
                        responses.append(
                            {
                                "url": response.url,
                                "status": response.status,
                                "ok": response.ok,
                            }
                        )

                active_page.on("response", record_response)
                try:
                    await button.click()
                    await active_page.wait_for_function(
                        """
                        () => document.querySelectorAll(
                            'input[type="number"]:not([disabled])'
                        ).length === 0
                        """,
                        timeout=120000,
                    )
                except Exception:
                    payload["estado"] = "guardado_incierto_no_reintentar"
                    payload["respuestas_guardado"] = responses
                    result_path.write_text(
                        json.dumps(payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    raise

                await active_page.wait_for_timeout(1500)
                payload["estado"] = "guardado"
                payload["confirmacion_guardado"] = "filas_cargadas_limpiadas"
                payload["respuestas_guardado"] = responses
                payload["url_final"] = active_page.url
                payload["texto_confirmacion"] = (
                    await active_page.locator("body").inner_text()
                )[-2000:]
                await active_page.screenshot(
                    path=str(ADJUSTMENT_DIR / "ultimo_ajuste_guardado.png"),
                    full_page=True,
                )
                result_path.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                return result_path
            return _save_result(payload)
        except Exception as exc:
            await _save_diagnostic(active_page, exc)
            raise
        finally:
            await browser.close()
