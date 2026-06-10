import asyncio
import msvcrt
import sys
import time

from credenciales import cargar, guardar
from flujo_ajuste import (
    aplicar,
    limpiar_descargas,
    preparar,
)
from informe_excel import guardar_informe_interactivo


def configurar_credenciales() -> dict:
    print()
    print("CONFIGURAR ACCESO A TIVENDO")
    email = input("Correo Tivendo: ").strip()
    password = input("Clave Tivendo (visible): ")
    if not email or not password:
        raise RuntimeError("Correo y clave son obligatorios.")
    guardar(email, password)
    print("Credenciales guardadas.")
    return {"email": email, "password": password}


def solicitar_cambio_credenciales(seconds: int = 5) -> bool:
    print()
    print(f"Presiona C para cambiar credenciales ({seconds} segundos).")
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if msvcrt.kbhit():
            key = msvcrt.getwch()
            return key.upper() == "C"
        time.sleep(0.1)
    return False


async def main() -> int:
    print("=" * 58)
    print(" STOCK NEGATIVO - LIBERTADOR 1476")
    print("=" * 58)
    print("Ejecucion automatica. Tivendo funcionara oculto.")

    configure_only = "--configurar" in sys.argv
    simulate_adjustment = "--simular-ajuste" in sys.argv
    prepare_only = "--solo-preparar" in sys.argv

    if configure_only:
        configurar_credenciales()
        return 0

    credentials = cargar()
    if not credentials:
        print()
        print("Primera ejecucion en este computador.")
        print("Las credenciales se solicitaran una sola vez.")
        try:
            credentials = configurar_credenciales()
        except Exception as exc:
            print(f"ERROR: {exc}")
            return 1
    elif solicitar_cambio_credenciales():
        try:
            credentials = configurar_credenciales()
        except Exception as exc:
            print(f"ERROR: {exc}")
            return 1

    visible = "--mostrar-navegador" in sys.argv

    try:
        print()
        print("Iniciando proceso...")
        if not prepare_only:
            inventory, articles, proposal, items = await preparar(
                credentials["email"],
                credentials["password"],
                visible=visible,
            )
            print()
            print(f"Inventario: {inventory}")
            print(f"Listado de articulos: {articles}")
            print(f"Propuesta: {proposal}")
            print(f"Articulos negativos validados: {len(items)}")

            result = await aplicar(
                credentials["email"],
                credentials["password"],
                items,
                visible=visible,
                simulate=simulate_adjustment,
            )
            print()
            if simulate_adjustment:
                print("SIMULACION COMPLETADA - NO SE MODIFICO STOCK")
            else:
                print("AJUSTE GUARDADO")
                print("Tivendo cerrado.")
                print("Selecciona donde guardar el informe Excel.")
                report = guardar_informe_interactivo(result, items)
                print(f"Informe guardado: {report}")
                deleted = limpiar_descargas(result)
                print(f"Descargas eliminadas: {len(deleted)}")
            print(f"Resultado: {result}")
            return 0

        inventory, articles, proposal, items = await preparar(
            credentials["email"],
            credentials["password"],
            visible=visible,
        )
    except Exception as exc:
        print()
        print(f"ERROR: {exc}")
        print("Se guardo un diagnostico en AppData\\Local\\TivendoStockNegativo\\diagnosticos")
        return 1

    print()
    print("PREPARACION COMPLETADA - NO SE MODIFICO STOCK")
    print(f"Inventario: {inventory}")
    print(f"Listado de articulos: {articles}")
    print(f"Propuesta: {proposal}")
    print(f"Articulos negativos validados: {len(items)}")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    if "--sin-pausa" not in sys.argv:
        input("\nPresiona ENTER para cerrar...")
    raise SystemExit(exit_code)
