@echo off
cd /d "%~dp0"
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not running or not installed.
  echo Start Docker Desktop with Linux containers, then try again.
  pause
  exit /b 1
)
echo Open http://localhost:3000 when OpenNet reports that it is running.
docker compose up --build
pause
