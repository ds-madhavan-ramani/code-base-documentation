#!/bin/bash

# Codebase Documentation System - Setup Script
# Run this to create the project structure

set -e

PROJECT_DIR="codebase-docs"
echo "🚀 Setting up $PROJECT_DIR..."

# Create project structure
mkdir -p "$PROJECT_DIR"/{app,core,utils,data/{uploads,outputs,cache},tests}

echo "✓ Directory structure created"

# Navigate to project
cd "$PROJECT_DIR"

# Initialize git (optional)
if [ ! -d .git ]; then
    git init
    cat > .gitignore << 'EOF'
venv/
.env
*.pyc
__pycache__/
.pytest_cache/
data/
*.egg-info/
dist/
build/
.DS_Store
EOF
    echo "✓ Git initialized with .gitignore"
fi

# Create Python virtual environment
if [ ! -d venv ]; then
    python3.11 -m venv venv
    echo "✓ Virtual environment created"
fi

# Activate venv
source venv/bin/activate
echo "✓ Virtual environment activated"

# Install requirements
echo "📦 Installing Python dependencies..."
pip install --upgrade pip setuptools wheel > /dev/null 2>&1

# Create requirements.txt if not exists
if [ ! -f requirements.txt ]; then
    cat > requirements.txt << 'EOF'
streamlit==1.37.0
gitpython==3.1.42
pygments==2.17.2
jinja2==3.1.2
markdown==3.5.2
requests==2.31.0
aiohttp==3.9.1
pydantic==2.5.3
python-dotenv==1.0.0
tree-sitter==0.21.0
tree_sitter_languages==1.10.2
EOF
    echo "✓ requirements.txt created"
fi

pip install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependencies installed"

# Create .env from template
if [ ! -f .env ]; then
    cat > .env << 'EOF'
# Remote Ubuntu Server (L40S)
ODYSSEUS_API_URL=http://UBUNTU_IP:8000
OLLAMA_API_URL=http://UBUNTU_IP:11434

# Local Paths
OUTPUT_DIR=./data/outputs
UPLOAD_DIR=./data/uploads
CACHE_DIR=./data/cache

# Debug Mode
DEBUG=true
EOF
    echo "✓ .env created (edit with your Ubuntu server IP)"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit .env and replace UBUNTU_IP with your Ubuntu server IP"
echo "2. Copy the Python files to their directories:"
echo "   - ollama_client.py → core/"
echo "   - odysseus_client.py → core/"
echo "   - code_parser.py → core/"
echo "   - doc_generator.py → core/"
echo "   - prompts.py → utils/"
echo "   - main.py → app/"
echo "   - integration_test.py → tests/"
echo ""
echo "3. Run integration test: python tests/integration_test.py"
echo "4. Launch app: streamlit run app/main.py"
echo ""
