@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "APP_NAME=Mistral Desktop Agent"
set "PORT=48723"

title %APP_NAME%

:menu
cls
echo ==========================================
echo   %APP_NAME%
echo ==========================================
echo.
echo  1. Installer ou mettre a jour
echo  2. Configurer les cles API
echo  3. Lancer l'application
echo  4. Quitter
echo.
set /p CHOICE=Choix: 

if "%CHOICE%"=="1" goto install
if "%CHOICE%"=="2" goto configure
if "%CHOICE%"=="3" goto launch
if "%CHOICE%"=="4" goto end
goto menu

:find_python
set "PYTHON_CMD="
where py >nul 2>nul
if %errorlevel%==0 set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  where python >nul 2>nul
  if %errorlevel%==0 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo.
  echo Python 3.11+ est requis.
  echo Telechargement: https://www.python.org/downloads/
  pause
  goto menu
)
%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if not %errorlevel%==0 (
  echo.
  echo Python doit etre en version 3.11 ou plus recente.
  %PYTHON_CMD% --version
  pause
  goto menu
)
exit /b 0

:install
call :find_python
echo.
echo Creation du venv...
%PYTHON_CMD% -m venv .venv
if not %errorlevel%==0 goto fail

call ".venv\Scripts\activate.bat"
echo Mise a jour de pip...
python -m pip install --upgrade pip
if not %errorlevel%==0 goto fail

echo Installation des dependances...
pip install -r requirements.txt
if not %errorlevel%==0 goto fail

echo Installation de Chromium pour Playwright...
python -m playwright install chromium
if not %errorlevel%==0 goto fail

echo.
echo Installation terminee.
echo Conseil: installe aussi Tesseract OCR pour Windows.
echo https://github.com/UB-Mannheim/tesseract/wiki
pause
goto menu

:configure
echo.
echo Configuration du fichier .env
call :write_env
if not %errorlevel%==0 goto fail
echo.
echo Configuration enregistree dans .env
pause
goto menu

:write_env
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$m=Read-Host 'MISTRAL_API_KEY';" ^
  "$t=Read-Host 'TELEGRAM_BOT_TOKEN optionnel';" ^
  "$v=Read-Host 'Activer le modele vision Mistral ? [true]'; if([string]::IsNullOrWhiteSpace($v)){$v='true'}; if($v -match '^(?i)(y|yes|oui|o|1|on)$'){$v='true'}; if($v -match '^(?i)(n|no|non|0|off)$'){$v='false'};" ^
  "$p=Read-Host 'Port web [48723]'; if([string]::IsNullOrWhiteSpace($p)){$p='48723'};" ^
  "$e=if([string]::IsNullOrWhiteSpace($t)){'false'}else{'true'};" ^
  "$home=[Environment]::GetFolderPath('UserProfile');" ^
  "$lines=@('MISTRAL_API_KEY='+$m,'MISTRAL_MODEL=mistral-large-latest','MISTRAL_MIN_SECONDS_BETWEEN_CALLS=20','MISTRAL_RATE_LIMIT_BACKOFF_SECONDS=60','MISTRAL_VISION_MODEL=pixtral-large-latest','ENABLE_VISION_MODEL='+$v,'VISION_EVERY_STEPS=3','TELEGRAM_BOT_TOKEN='+$t,'ENABLE_TELEGRAM='+$e,'HOST=0.0.0.0','PORT='+$p,'DATABASE_PATH=data/agent_memory.sqlite3','SCREENSHOT_PATH=data/latest_screenshot.png','IMPORTANT_CAPTURE_DIR=data/captures','SCREENSHOT_BACKEND=auto','FILE_ACCESS_MODE=full','ALLOWED_FILE_ROOTS=','TERMINAL_WORKDIR='+$home,'SEARCH_ENGINE=duckduckgo','MAX_STEPS=50','MAX_RUNTIME_SECONDS=7200','MAX_RETRIES=3','LOOP_DELAY_SECONDS=1.0','MAX_REPEATED_ACTIONS=3','MAX_STAGNANT_OBSERVATIONS=3','CHECKPOINT_EVERY_STEPS=1','TERMINAL_TIMEOUT_SECONDS=30','BROWSER_HEADLESS=false');" ^
  "Set-Content -Path '.env' -Value $lines -Encoding UTF8"
exit /b %errorlevel%

:launch
if not exist ".venv\Scripts\activate.bat" (
  echo.
  echo L'application n'est pas encore installee.
  echo Lance d'abord l'option 1.
  pause
  goto menu
)
if not exist ".env" (
  echo.
  echo Le fichier .env manque. Configuration maintenant.
  call :write_env
  if not %errorlevel%==0 goto fail
)
call ".venv\Scripts\activate.bat"
for /f "tokens=2 delims==" %%A in ('findstr /B "PORT=" .env 2^>nul') do set "PORT=%%A"
echo.
echo Ouverture de http://127.0.0.1:%PORT%
powershell -NoProfile -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:%PORT%'" >nul 2>nul
python main.py
pause
goto menu

:fail
echo.
echo Une erreur est survenue.
pause
goto menu

:end
endlocal
