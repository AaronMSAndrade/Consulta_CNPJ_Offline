@echo off
cd /d %~dp0
if not exist servidor.pid (
  echo Nenhum registro de app oculto. Se estiver aberto em janela, feche com Ctrl+C.
  pause
  exit /b
)
set /p PID=<servidor.pid
tasklist /FI "PID eq %PID%" 2>nul | find /I "python" >nul
if errorlevel 1 (
  echo Registro desatualizado - o app ja estava fechado. Limpando.
  del servidor.pid
  pause
  exit /b
)
taskkill /PID %PID% /T /F >nul 2>&1
del servidor.pid >nul 2>&1
echo App encerrado.
pause
