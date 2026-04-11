#!/bin/bash
# Enviroments - Build Script (Linux/macOS)
# Prerequisites: pip install pyinstaller pnpm

set -e

echo "==> Building frontend..."
cd frontend
pnpm install
pnpm run build
cd ..

echo "==> Building executable..."
pyinstaller Enviroments.spec --noconfirm

echo ""
echo "========================================"
echo "Build complete!"
echo "Output: dist/Enviroments/"
echo ""
echo "Run: ./dist/Enviroments/Enviroments"
echo "========================================"
