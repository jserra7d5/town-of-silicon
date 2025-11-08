# Town of Silicon

Single-player Town of Salem with 14 AI agents powered by oss-20b (64K context).

## Key Features

- **64K Context Window**: Complete game history, no summarization needed
- **Perfect AI Memory**: AIs remember every chat message, vote, and death
- **20B Parameter Model**: High-quality decision making and natural language
- **M4 Pro Optimized**: Metal acceleration for maximum performance
- **Canvas-based UI**: Chatbot-centric interface with role action buttons

## System Requirements

- **Hardware**: Apple Silicon (M4 Pro recommended) with 48GB+ RAM
- **Software**: Python 3.11+, Node.js 18+

## Quick Start

### 1. Download the Model

```bash
# Create models directory
mkdir -p models
cd models

# Download oss-20b Q4_K_M (~11GB)
# Option A: Using huggingface-cli
huggingface-cli download TheBloke/OSS-20B-GGUF \
  oss-20b.Q4_K_M.gguf \
  --local-dir . \
  --local-dir-use-symlinks False

# Option B: Manual download
# Visit: https://huggingface.co/TheBloke/OSS-20B-GGUF
# Download: oss-20b.Q4_K_M.gguf

cd ..
```

### 2. Install Backend Dependencies

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install llama-cpp-python with Metal support (M4 Pro)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir

cd ..
```

### 3. Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit .env to set model path
echo "LLM_MODEL_PATH=../models/oss-20b.Q4_K_M.gguf" >> backend/.env
```

### 4. Run the Backend

```bash
cd backend
python main.py

# Server will start on http://localhost:8000
# API docs: http://localhost:8000/docs
```

### 5. Run the Frontend

```bash
cd frontend
pnpm install
pnpm dev

# Frontend will start on http://localhost:5173
```

## Project Structure

```
town-of-silicon/
├── backend/               # Python FastAPI backend
│   ├── core/             # Game logic systems
│   ├── ai/               # AI players with 64K context
│   ├── models/           # Pydantic data models
│   ├── api/              # WebSocket & REST APIs
│   └── main.py           # Application entry point
│
├── frontend/             # Canvas-based UI
│   ├── src/
│   │   ├── canvas/      # Canvas rendering engine
│   │   ├── ui/          # UI components (chat, buttons)
│   │   └── api/         # WebSocket client
│   └── index.html
│
├── models/              # LLM models (gitignored)
│   └── oss-20b.Q4_K_M.gguf
│
└── docs/                # Specifications
    ├── ARCHITECTURE.md
    └── specs/
```

## Memory Configuration

### Optimal Settings for M4 Pro 48GB

```
Total Memory:          48 GB
────────────────────────────
macOS System:           8 GB
Model (20B Q4):        11 GB
KV Cache (64K ctx):    24 GB
Batch processing:       3 GB
Buffer:                 2 GB

Context Window:     64,000 tokens
                    (~48,000 words)
                    = ENTIRE game fits!
```

## Performance Expectations

### M4 Pro with oss-20b Q4_K_M

- **Model Loading**: 8-12 seconds (first time)
- **Night Phase**: ~16 seconds (all 14 AIs decide)
- **Chat Message**: ~1.5-2 seconds per AI
- **Vote Decision**: ~1 second per AI
- **Context Switch**: 25-35ms (negligible!)

### Batching

- Batch size: 4 AIs simultaneously
- Total batches: 4 (for 14 AIs)
- Time per batch: ~4 seconds
- **Total night: ~16 seconds**

## Development

### Backend

```bash
# Run with hot reload
cd backend
uvicorn main:app --reload

# Run tests
pytest

# Type checking
mypy .

# Linting
ruff check .
ruff format .
```

### Frontend

```bash
cd frontend

# Development server
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview
```

## Architecture Highlights

### 64K Context = No Summarization

Traditional LLM games struggle with memory:
- Small context (8K): Must summarize aggressively
- Information loss: AIs forget important details
- Inconsistent behavior: AIs contradict themselves

**Town of Silicon with 64K context:**
- ✅ Complete chat history (all messages)
- ✅ Complete vote history (every trial)
- ✅ All deaths with full wills
- ✅ All investigation results
- ✅ Perfect memory - AIs never forget

### AI Context Example

```python
# Typical Town of Salem game fits in ~20-30K tokens:
{
  "system_prompt": "500 tokens",
  "role_info": "300 tokens",
  "chat_history": "15,000 tokens",  # ALL messages
  "vote_history": "2,000 tokens",   # ALL votes
  "deaths_wills": "3,000 tokens",   # ALL deaths
  "investigations": "1,500 tokens",  # ALL results
  "ai_memory": "3,000 tokens"       # Suspicions, notes
}

Total: ~26,000 tokens
Remaining: 38,000 tokens (room to grow!)
```

## Troubleshooting

### Model Not Loading

```bash
# Verify model path
ls -lh models/oss-20b.Q4_K_M.gguf

# Check Metal support
python -c "from llama_cpp import Llama; print('Metal supported!')"

# Rebuild with Metal
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
```

### Out of Memory

```bash
# Check memory usage
Activity Monitor > Memory tab

# Reduce context size in .env
LLM_CONTEXT_SIZE=32768  # Reduce to 32K if needed

# Reduce batch size
AI_BATCH_SIZE=2  # Process 2 AIs at once instead of 4
```

### Slow Performance

```bash
# Ensure Metal acceleration is working
# Check logs for: "Using Metal"

# Reduce model size (if needed)
# Download oss-14b instead of oss-20b

# Adjust threads
LLM_N_THREADS=8  # Reduce if needed
```

## License

MIT

## Credits

- Game Design: BlankMediaGames (Town of Salem)
- LLM: oss-20b via llama.cpp
- Framework: FastAPI + Pydantic AI
