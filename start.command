
#!/bin/bash

cd "$(dirname "$0")" || exit 1

echo "Checking Pillow RAQM support..."

uv run python -c "from PIL import features; print('RAQM:', features.check_feature('raqm'))"

if [ $? -ne 0 ]; then
    echo "Failed to check Pillow."
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "Starting Dhamma Studio..."

uv run python server.py

echo ""
read -p "Press Enter to exit..."
