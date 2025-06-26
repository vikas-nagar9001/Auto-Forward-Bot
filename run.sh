#!/bin/bash

# Auto Message Forwarder Bot - Run Script
# This script installs dependencies and starts the bot

echo "🚀 Starting Auto Message Forwarder Bot..."
echo "==========================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "❌ Error: Python is not installed or not in PATH"
    echo "Please install Python 3.7+ and try again"
    exit 1
fi

# Use python3 if available, otherwise use python
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PIP_CMD="pip3"
else
    PYTHON_CMD="python"
    PIP_CMD="pip"
fi

echo "✅ Python found: $($PYTHON_CMD --version)"

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.7"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python $PYTHON_VERSION is installed, but Python $REQUIRED_VERSION+ is required"
    exit 1
fi

echo "✅ Python version check passed"

# Install requirements
echo ""
echo "📦 Installing dependencies..."
echo "----------------------------"

if [ -f "requirements.txt" ]; then
    $PIP_CMD install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "❌ Error: Failed to install requirements"
        echo "Please check your internet connection and try again"
        exit 1
    fi
    echo "✅ Dependencies installed successfully"
else
    echo "❌ Error: requirements.txt not found"
    echo "Please make sure you're in the correct directory"
    exit 1
fi

# Check if config.py exists
echo ""
echo "🔧 Checking configuration..."
echo "----------------------------"

if [ ! -f "config.py" ]; then
    echo "❌ Warning: config.py not found"
    echo "Please make sure you have configured your environment variables:"
    echo "  - API_ID (Telegram API ID)"
    echo "  - API_HASH (Telegram API Hash)"
    echo "  - BOT_TOKEN (Telegram Bot Token)"
    echo "  - MONGO_URI (MongoDB Connection URI)"
    echo ""
    echo "You can also create a config.py file with these variables"
    echo "Continuing anyway (assuming environment variables are set)..."
else
    echo "✅ Configuration file found"
fi

# Start the bot
echo ""
echo "🤖 Starting the bot..."
echo "---------------------"

if [ -f "main.py" ]; then
    echo "Bot is starting up..."
    echo "Press Ctrl+C to stop the bot"
    echo ""
    $PYTHON_CMD main.py
else
    echo "❌ Error: main.py not found"
    echo "Please make sure you're in the correct directory"
    exit 1
fi
