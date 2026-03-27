#!/bin/bash

echo "🚀 Starting Statement Processor Setup..."
echo ""

cd "$(dirname "$0")"

# Try to use existing Python
echo "📦 Installing Streamlit (this may take a minute)..."
python3 -m pip install streamlit pandas --quiet --disable-pip-version-check 2>/dev/null

if [ $? -eq 0 ]; then
    echo "✅ Dependencies installed!"
    echo ""
    echo "🎉 Starting Streamlit app..."
    echo "    The app will open at: http://localhost:8501"
    echo ""
    python3 -m streamlit run app.py
else
    echo "❌ Installation had issues. Try running manually:"
    echo ""
    echo "   python3 -m pip install streamlit pandas"
    echo "   python3 -m streamlit run app.py"
fi
