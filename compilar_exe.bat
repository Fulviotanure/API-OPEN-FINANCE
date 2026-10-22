@echo off
title Compilando Pluggy Explorer para Executavel (.exe)
echo ========================================================
echo   COMPILANDO PLUGGY OPEN FINANCE EXPLORER (.EXE)
echo ========================================================
echo.
cd /d "%~dp0"
echo Executando PyInstaller...
python -m PyInstaller --noconsole --onefile --icon="app_icon.ico" --name="PluggyExplorer" --collect-all customtkinter app_explorer.py
echo.
if exist "dist\PluggyExplorer.exe" (
    echo [SUCESSO] Executavel gerado em dist\PluggyExplorer.exe!
    copy /y "dist\PluggyExplorer.exe" "PluggyExplorer.exe"
    echo [SUCESSO] Atualizado na pasta raiz: PluggyExplorer.exe
) else (
    echo [ERRO] Houve uma falha na compilacao. Verifique as mensagens acima.
)
pause
