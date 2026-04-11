# Enviroments - Build Script
# Run on Windows to generate a standalone .exe

# Prerequisites:
#   pip install pyinstaller
#   (Node.js and pnpm for frontend rebuild only)

# Step 1: Build frontend
echo Building frontend...
cd frontend
call pnpm install
call pnpm run build
cd ..

# Step 2: Build Windows executable
echo Building Windows executable...
pyinstaller Enviroments.spec --noconfirm

echo.
echo ========================================
echo Build complete!
echo Output: dist/Enviroments/
echo   - Enviroments.exe  (main executable)
echo.
echo Run: dist\Enviroments\Enviroments.exe
echo ========================================
