@echo off
REM ---------------------------------------------------------------------------
REM Abre o app no LAYOUT DE CELULAR rodando no computador, para testar a tela
REM do celular sem esperar o build do APK. Na primeira vez cria o ambiente e
REM instala as dependencias (demora alguns minutos); depois abre em segundos.
REM
REM Dica: depois de abrir, ESTREITE a janela para ela ficar parecida com um
REM telefone (retrato).
REM ---------------------------------------------------------------------------
cd /d "%~dp0"

echo === Previa do layout de celular (Gestao de Arranjo) ===
echo.

if not exist "venv\Scripts\python.exe" (
    echo Primeira execucao: criando o ambiente virtual...
    python -m venv venv
    if errorlevel 1 (
        echo.
        echo ERRO: nao foi possivel criar o ambiente. O Python esta instalado?
        pause
        exit /b 1
    )
    echo Instalando dependencias, aguarde alguns minutos...
    venv\Scripts\python.exe -m pip install --upgrade pip
    venv\Scripts\python.exe -m pip install -r src\requirements.txt
    if errorlevel 1 (
        echo.
        echo ERRO: falha ao instalar as dependencias.
        pause
        exit /b 1
    )
)

set GA_FORCAR_MOBILE=1
echo.
echo Abrindo o app no layout de celular...
echo (Estreite a janela para simular a tela de um telefone.)
echo.
venv\Scripts\python.exe src\main.py

if errorlevel 1 (
    echo.
    echo O aplicativo encerrou com erro.
    pause
)
