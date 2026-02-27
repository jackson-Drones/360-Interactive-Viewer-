@echo off
cd /d "%~dp0"
echo.
echo ========================================
echo   360 Virtual Experience Viewer
echo ========================================
echo.
echo Starting server...
echo.
timeout /t 2 /nobreak >nul
start "" "http://localhost:8080/viewer/multi-view.html"
python server.py 8080
