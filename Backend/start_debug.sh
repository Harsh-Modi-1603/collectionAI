#!/bin/bash

echo "================================"
echo "DEBUG: Starting CollectionAI Backend"
echo "================================"
echo "Current directory: $(pwd)"
echo "Directory contents:"
ls -la
echo "================================"
echo "Python version: $(python --version)"
echo "PORT: $PORT"
echo "================================"
echo "Checking if app module exists:"
python -c "import sys; print('Python path:', sys.path)" 2>&1
echo "================================"
echo "Trying to import app.main:"
python -c "from app import main; print('SUCCESS: app.main imported')" 2>&1
echo "================================"
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT
