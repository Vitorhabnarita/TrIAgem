@echo off
chcp 65001 >nul
echo ===================================================================
echo   TrIAgem VetTech v6.0 - Inicializacao Automatica do Ambiente Local
echo ===================================================================
cd /d "%~dp0"

echo [1/4] Verificando PostgreSQL portatil (.pgtest na porta 54329)...
.\.pgtest\pgsql\bin\pg_ctl.exe status -D .\.pgtest\pgdata >nul 2>&1
if errorlevel 1 (
    .\.pgtest\pgsql\bin\pg_ctl.exe start -D .\.pgtest\pgdata -o "-p 54329" -l .\.pgtest\pg.log
)

echo [2/4] Aplicando migracoes Alembic (001 a 004) e Seed Demo...
.\venv\Scripts\alembic.exe upgrade head
.\venv\Scripts\python.exe scripts\seed.py --demo

echo [3/4] Iniciando Backend FastAPI na porta 8000...
start "TrIAgem Backend (FastAPI :8000)" cmd /k ".\venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000"

echo [4/4] Iniciando Frontend React/Vite na porta 5173...
start "TrIAgem Frontend (Vite :5173)" cmd /k "cd /d "%~dp0frontend" && npm.cmd run dev"

echo.
echo Sistema iniciado! Acesse: http://localhost:5173
