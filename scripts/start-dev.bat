@echo off
REM One-click dev: backend (reload) + Vite + Electron z ASSYSTENT_DEV=1
REM Umieszczenie: scripts\ — repo root NADRZĘDNY względem tego katalogu.
REM Wymaga: LM Studio (lub inny endpoint LLM) wg docs/ENV_SETUP.md §8.1 — uruchom ręcznie przed lub po backendzie.

setlocal EnableExtensions

chcp 65001 >nul 2>nul

cd /d "%~dp0.." || exit /b 1
set "ROOT=%CD%"

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo [BLED] Brak srodowiska .venv w "%ROOT%". Uruchom raz ^(skopiuj cala linie^):
  echo   powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
  exit /b 1
)

"%ROOT%\.venv\Scripts\python.exe" -c "import multipart" 2>nul
if errorlevel 1 (
  echo [INFO] Brak pakietu python-multipart — doinstalowuje ^(FastAPI UploadFile /voice/transcribe^)...
  "%ROOT%\.venv\Scripts\python.exe" -m pip install "python-multipart>=0.0.9"
  if errorlevel 1 (
    echo [BLED] pip install python-multipart nie powiodl sie.
    exit /b 1
  )
)

if not exist "%ROOT%\frontend\node_modules" (
  echo [INFO] frontend\node_modules — pierwszy raz: npm ci ...
  pushd "%ROOT%\frontend"
  call npm ci
  if errorlevel 1 popd & exit /b 1
  popd
)

echo [OK] Repo: "%ROOT%"
echo [OK] Otwieram 3 okna: backend na :8000, Vite na :5173, Electron ^(DEV^).

start "Assystent — backend" cmd /k "cd /d ""%ROOT%"" && call .venv\Scripts\activate.bat && uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload & pause"

timeout /t 2 /nobreak >nul

start "Assystent — Vite" cmd /k "cd /d ""%ROOT%\frontend"" && npm run dev & pause"

timeout /t 5 /nobreak >nul

start "Assystent — Electron" cmd /k "cd /d ""%ROOT%\frontend"" && set ASSYSTENT_DEV=1 && npm run electron & pause"

echo.
echo Gotowe. Jesli Electron zglosi pusty ekran, poczekaj na Vite lub odswiez okno po kilku sekundach.
echo Zamknij kazde z trzech okien CMD, aby zatrzymac dany proces .
endlocal
