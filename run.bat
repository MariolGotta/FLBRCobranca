@echo off
title FLBR Corp - Sistema de Cobranca
echo.
echo ========================================
echo   FLBR Corp - Sistema de Cobranca
echo ========================================
echo.

cd /d "%~dp0"

REM Check if database exists, if not run import
if not exist "database\flbr.db" (
    echo [PRIMEIRO USO] Banco de dados nao encontrado.
    echo Iniciando importacao dos arquivos Excel...
    echo.
    python import_excel.py
    echo.
)

echo Iniciando servidor...
echo Acesse: http://localhost:5000
echo.
echo Para encerrar, pressione Ctrl+C nesta janela.
echo.
start "" "http://localhost:5000"
python app.py
pause
