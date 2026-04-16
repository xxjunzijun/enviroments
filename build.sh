#!/bin/bash
# Enviroments - Build Script (Linux/macOS)
# Prerequisites: Python, Node.js, pnpm, and pip install pyinstaller

set -e

echo "==> Building frontend..."
cd frontend
pnpm install
pnpm run build
cd ..

echo "==> Building executable..."
cd backend
pyinstaller Enviroments.spec --noconfirm --clean --distpath ../dist --workpath ../build
cd ..

echo ""
echo "========================================"
echo "Build complete!"
echo "Output: dist/Enviroments/"
echo ""
echo "Run: ./dist/Enviroments/Enviroments"
echo "========================================"
