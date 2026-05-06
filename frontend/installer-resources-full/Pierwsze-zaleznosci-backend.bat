@echo off
chcp 65001 >nul
setlocal
set "PYAPP=%~dp0..\python-app"
if not exist "%PYAPP%\backend\main.py" (
  echo [BŁĄD] Nie znaleziono bundlowanego backendu w:
  echo   %PYAPP%
  echo Uruchom ten plik z katalogu: resources\bundled\docs
  pause
  exit /b 1
)
cd /d "%PYAPP%" || exit /b 1
echo [OK] Katalog backendu: %CD%
where python >nul 2>nul
if errorlevel 1 (
  echo [BŁĄD] Brak „python” w PATH. Zainstaluj Python 3.11+ i zaznacz „Add to PATH”.
  pause
  exit /b 1
)
python -m pip install --upgrade pip
if errorlevel 1 goto :err
python -m pip install -r requirements.txt
if errorlevel 1 goto :err
echo.
echo [OK] Zależności zainstalowane. Uruchom „Assystent Komplet” ponownie.
pause
exit /b 0
:err
echo [BŁĄD] pip zakończył się niepowodzeniem.
pause
exit /b 1
