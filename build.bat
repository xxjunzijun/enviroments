@echo off
REM Enviroments - Build Script for Windows
REM Prerequisites: pip install pyinstaller, Node.js, pnpm

echo Building frontend...
cd /d "%~dp0frontend"
call pnpm install
call pnpm run build
cd /d "%~dp0"

echo Building Windows executable...
pyinstaller Enviroments.spec --noconfirm

echo.
echo ========================================
echo Build complete!
echo Output: dist\Enviroments\
echo.
echo Run: dist\Enviroments\Enviroments.exe
echo ========================================
