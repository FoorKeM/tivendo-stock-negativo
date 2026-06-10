# Tivendo Stock Negativo

Automatiza el ajuste positivo de artículos con stock negativo en la bodega
`LIBERTADOR 1476` de Tivendo.

## Seguridad del flujo

- Solo procesa códigos que comienzan con `A`.
- Solo carga artículos cuyo stock actual es estrictamente negativo.
- Omite positivos, ceros y códigos `P`.
- Valida código, nombre y código de barra antes de cargar cada artículo.
- Genera un Excel final únicamente con los artículos realmente ajustados.
- Las credenciales se guardan localmente en cada computador y nunca forman
  parte del repositorio ni del ejecutable.

## Uso

1. Descarga `TivendoStockNegativoPortable.exe` desde la sección Releases.
2. Ejecuta el archivo.
3. En la primera ejecución ingresa las credenciales de Tivendo.
4. Para cambiarlas posteriormente, presiona `C` durante los primeros cinco
   segundos.
5. Al finalizar, selecciona dónde guardar el informe Excel.

Edge o Chrome se ejecutan ocultos. La ventana de CMD muestra el progreso.

## Desarrollo

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m PyInstaller TivendoStockNegativo.spec --clean --noconfirm
```

Cada cambio enviado a `main` ejecuta las pruebas, construye el EXE en Windows
y publica automáticamente una nueva versión `v1.0.N` en GitHub Releases.

