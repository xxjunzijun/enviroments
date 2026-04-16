@echo off
REM Enviroments - Build Script for Windows
REM Prerequisites: Python, Node.js, pnpm, and pip install pyinstaller

echo Building frontend...
cd /d "%~dp0frontend"
call pnpm install
call pnpm run build

echo Building Windows executable...
cd /d "%~dp0backend"
pyinstaller Enviroments.spec --noconfirm --clean --distpath "%~dp0dist" --workpath "%~dp0build"
cd /d "%~dp0"

echo.
echo ========================================
echo Build complete!
echo Output: dist\Enviroments\
echo.
echo Run: dist\Enviroments\Enviroments.exe
echo ========================================
