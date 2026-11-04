@echo off
setlocal
cd /d "%~dp0"

set "APP_NAME=Wifi CopyPate"
set "ENTRY_SCRIPT=wifi.py"
set "VENV_DIR=.venv"

if not exist "%ENTRY_SCRIPT%" (
  echo Erro: nao encontrei %ENTRY_SCRIPT% em:
  echo %CD%
  echo Coloque build_windows.bat na mesma pasta de wifi.py ou ajuste ENTRY_SCRIPT.
  exit /b 1
)

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON=py -3"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo Erro: Python 3 nao foi encontrado. Instale-o e tente novamente.
    exit /b 1
  )
  set "PYTHON=python"
)

if not exist "%VENV_DIR%\Scripts\python.exe" (
  %PYTHON% -m venv "%VENV_DIR%"
  if errorlevel 1 exit /b 1
)

call "%VENV_DIR%\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

if exist "requirements.txt" (
  python -m pip install -r requirements.txt
  if errorlevel 1 exit /b 1
) else (
  echo Aviso: requirements.txt nao existe; pulando instalacao de dependencias do projeto.
)

python -m pip install --upgrade pyinstaller
if errorlevel 1 exit /b 1

python -m PyInstaller --clean --noconfirm --onedir --name "%APP_NAME%" "%ENTRY_SCRIPT%"
if errorlevel 1 exit /b 1

echo.
echo Build concluido. Saida: %CD%\dist\%APP_NAME%
echo Teste o aplicativo dentro da pasta dist antes de distribuir.
endlocal
