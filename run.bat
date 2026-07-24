@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\activate.bat" (
    echo ERRO: Ambiente virtual nao encontrado.
    echo Execute: python -m venv venv
    pause
    exit /b 1
)

call venv\Scripts\activate.bat
python src\main.py

if errorlevel 1 (
    echo.
    echo O aplicativo encerrou com erro.
    pause
)