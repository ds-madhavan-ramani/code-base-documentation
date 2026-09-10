#!/bin/bash
# Quick installation script for Ollama and vLLM on Ubuntu

set -e  # Exit on error

echo "========================================"
echo "  Installing Ollama & vLLM on Ubuntu"
echo "========================================"
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if running on Ubuntu
if ! grep -qi ubuntu /etc/os-release; then
    echo "This script is designed for Ubuntu. Continuing anyway..."
fi

# ============================================
# PART 1: CUDA 12.4
# ============================================
echo -e "${BLUE}[1/3] Installing CUDA 12.4...${NC}"
echo ""

cd /tmp

# Download CUDA keyring
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb

# Install keyring
sudo dpkg -i cuda-keyring_1.1-1_all.deb

# Update package list
sudo apt-get update

# Install CUDA
echo "Installing CUDA Toolkit 12.4 (this may take 10-20 minutes)..."
sudo apt-get install -y cuda-toolkit-12-4 cuda-runtime-12-4

# Add CUDA to PATH
echo 'export PATH=/usr/local/cuda-12.4/bin:$PATH' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.4/lib64:$LD_LIBRARY_PATH' >> ~/.bashrc
source ~/.bashrc

# Verify CUDA
echo ""
echo -e "${GREEN}✓ CUDA 12.4 installed${NC}"
nvcc --version
nvidia-smi

# ============================================
# PART 2: OLLAMA
# ============================================
echo ""
echo -e "${BLUE}[2/3] Installing Ollama...${NC}"
echo ""

curl -fsSL https://ollama.ai/install.sh | sh

# Create models directory
mkdir -p /mnt/ollama_models
echo 'export OLLAMA_MODELS=/mnt/ollama_models' >> ~/.bashrc
source ~/.bashrc

# Start Ollama in background
echo "Starting Ollama..."
ollama serve &
OLLAMA_PID=$!
sleep 3

# Verify Ollama is running
if curl -s http://localhost:11434/api/tags > /dev/null; then
    echo -e "${GREEN}✓ Ollama running on localhost:11434${NC}"
else
    echo "Warning: Ollama may not be running properly"
fi

# ============================================
# PART 3: vLLM
# ============================================
echo ""
echo -e "${BLUE}[3/3] Installing vLLM...${NC}"
echo ""

# Install Python 3.11
sudo apt-get install -y python3.11 python3.11-venv python3.11-dev

# Create vLLM environment
python3.11 -m venv /opt/vllm
source /opt/vllm/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install vLLM with CUDA support
echo "Installing vLLM (this may take 10-15 minutes)..."
pip install vllm[cuda12]

# Create server script
cat > /opt/vllm/run_server.sh << 'EOFSCRIPT'
#!/bin/bash
source /opt/vllm/bin/activate
python -m vllm.entrypoints.openai.api_server \
  --model mistral \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.9 \
  --port 8000
EOFSCRIPT

chmod +x /opt/vllm/run_server.sh

# Verify vLLM
python -c "import vllm; print('✓ vLLM version:', vllm.__version__)"

echo -e "${GREEN}✓ vLLM installed${NC}"

# ============================================
# SUMMARY
# ============================================
echo ""
echo "========================================"
echo -e "${GREEN}✓ Installation Complete!${NC}"
echo "========================================"
echo ""
echo "CUDA 12.4:"
echo "  nvcc --version"
echo ""
echo "Ollama (running on localhost:11434):"
echo "  ollama list"
echo "  ollama pull mistral"
echo "  curl http://localhost:11434/api/tags"
echo ""
echo "vLLM (ready to run):"
echo "  source /opt/vllm/bin/activate"
echo "  /opt/vllm/run_server.sh"
echo "  curl http://localhost:8000/v1/models"
echo ""
echo "Next steps:"
echo "  1. Pull a model: ollama pull mistral"
echo "  2. Start vLLM: /opt/vllm/run_server.sh &"
echo "  3. Test: curl http://localhost:8000/v1/models"
echo ""

