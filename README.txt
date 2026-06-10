STOCK NEGATIVO - LIBERTADOR 1476

Usa solamente:
portable\TivendoStockNegativoPortable.exe

Al abrirlo, el proceso completo comienza automaticamente.
Solo se muestra la ventana de CMD con el progreso.
Tivendo y el navegador funcionan ocultos.

En cada computador nuevo, la primera ejecucion solicita el correo y la
clave de Tivendo una sola vez. Luego quedan guardados localmente en ese PC.

Para cambiar las credenciales en el futuro, abre el mismo EXE y presiona C
durante los primeros 5 segundos. Ingresa el correo y la nueva clave.

El programa descarga inventario y listado de articulos, cruza
CodArticulo con Codigo barra interno y ajusta solamente codigos A con
stock actual negativo.

Al finalizar y cerrar Tivendo, pregunta donde guardar un informe Excel.
Ese informe contiene exclusivamente los negativos realmente ajustados y
las cantidades aplicadas. No vuelve a entrar a Tivendo ni descarga un
inventario posterior.

Para editar las credenciales, ejecuta el EXE con --configurar.
Los positivos, ceros y codigos P se omiten siempre.

Los archivos descargados quedan en:
%LOCALAPPDATA%\TivendoStockNegativo\descargas

Las propuestas y resultados quedan en:
%LOCALAPPDATA%\TivendoStockNegativo\ajustes

Despues de un ajuste guardado y verificado correctamente, se eliminan
todos los archivos de la carpeta descargas. En preparaciones, simulaciones
o ejecuciones con error, se conservan para diagnostico.

Los diagnosticos quedan en:
%LOCALAPPDATA%\TivendoStockNegativo\diagnosticos

Es independiente y no lee ni modifica archivos de mercadohouse_sync.
