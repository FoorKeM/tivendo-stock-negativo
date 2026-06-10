@echo off
setlocal
cd /d "%~dp0"
python -m PyInstaller TivendoStockNegativo.spec --clean --noconfirm
if errorlevel 1 (
  echo ERROR AL CONSTRUIR
  pause
  exit /b 1
)
echo.
echo EXE CREADO EN:
echo %~dp0dist\TivendoStockNegativoPortable.exe
pause
