@echo off
setlocal
set "VENV=%LOCALAPPDATA%\MeshcoreTracker\.venv"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "%VENV%\Scripts\python.exe" (
    echo Preparando o ambiente Python...
    py -3 -m venv "%VENV%"
    if errorlevel 1 (
        echo Nao foi possivel criar o ambiente. Instale o Python 3.10 ou mais novo em python.org.
        pause
        exit /b 1
    )
)

"%VENV%\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo Nao foi possivel instalar as dependencias. Verifique a internet.
    pause
    exit /b 1
)

"%VENV%\Scripts\python.exe" "%~dp0app.py" %*
if errorlevel 1 pause
