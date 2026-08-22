@echo off
rem ============================================================
rem  PySusNoCode - iniciar o aplicativo
rem  Na primeira execucao, cria o ambiente Python e instala tudo.
rem ============================================================
setlocal
pushd "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Primeira execucao: preparando o ambiente Python. Isso demora alguns minutos...
    where py >nul 2>nul && (py -3 -m venv .venv) || (python -m venv .venv)
    if not exist ".venv\Scripts\python.exe" (
        echo ERRO: Python nao encontrado. Instale o Python 3.10+ em https://python.org
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

start "PySusNoCode" ".venv\Scripts\pythonw.exe" -m pysusnocode
popd
