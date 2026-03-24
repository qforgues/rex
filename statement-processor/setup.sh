#!/bin/bash

echo "🚀 Setting up Statement Processor..."
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7 or later."
    exit 1
fi

echo "✅ Python found: $(python3 --version)"
echo ""

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Check for accounts.json
if [ ! -f "accounts.json" ]; then
    echo ""
    echo "⚠️  accounts.json not found in this directory."
    echo "   To use the app, copy your accounts.json file here:"
    echo "   cp ../Financial\ Statements/accounts.json ."
    echo ""
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "To start the app, run:"
echo "   source venv/bin/activate"
echo "   streamlit run app.py"
echo ""
