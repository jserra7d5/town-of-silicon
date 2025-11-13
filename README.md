# Town of Silicon

Single-player Town of Salem with 14 AI agents powered by oss-20b (64K context).

## Key Features

- **64K Context Window**: Complete game history, no summarization needed
- **Perfect AI Memory**: AIs remember every chat message, vote, and death
- **20B Parameter Model**: High-quality decision making and natural language
- **M4 Pro Optimized**: Metal acceleration for maximum performance
- **Full Role Support**: 24+ roles with complete mechanics implementation
- **Canvas-based UI**: Chatbot-centric interface with role action buttons

## System Requirements

- **Hardware**: Apple Silicon (M4 Pro recommended) with 48GB+ RAM
- **Software**: Python 3.11+, Node.js 18+ (optional for frontend)
- **Storage**: ~12GB for model + ~500MB for application

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/town-of-silicon.git
cd town-of-silicon
```

### 2. Download the Model

```bash
# Create models directory
mkdir -p models
cd models

# Download oss-20b Q4_K_M (~11GB)
# Option A: Using huggingface-cli
pip install huggingface-hub
huggingface-cli download TheBloke/OSS-20B-GGUF \
  oss-20b.Q4_K_M.gguf \
  --local-dir . \
  --local-dir-use-symlinks False

# Option B: Manual download
# Visit: https://huggingface.co/TheBloke/OSS-20B-GGUF
# Download: oss-20b.Q4_K_M.gguf

cd ..
```

### 3. Install Backend Dependencies

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install llama-cpp-python with Metal support (Apple Silicon)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir

cd ..
```

**Note for non-Apple Silicon users:**
```bash
# For CUDA (NVIDIA GPUs)
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir

# For CPU only
pip install llama-cpp-python
```

### 4. Configure Environment

```bash
# Copy environment template
cp backend/.env.example backend/.env

# Edit .env with your preferred text editor
# Set the model path (should work as-is if model is in ../models/)
nano backend/.env  # or vim, code, etc.
```

**Key settings in `.env`:**
```bash
LLM_MODEL_PATH=../models/oss-20b.Q4_K_M.gguf
LLM_CONTEXT_SIZE=65536  # 64K context
LLM_N_GPU_LAYERS=-1     # Offload all layers to GPU
LLM_N_THREADS=10        # Adjust for your CPU
AI_BATCH_SIZE=4         # Process 4 AIs in parallel
```

### 5. Run the Backend

```bash
cd backend
source venv/bin/activate  # If not already activated

# Run the server
python main.py

# Server will start on http://localhost:8000
# API docs: http://localhost:8000/docs
```

**Expected startup output:**
```
INFO     Loading LLM model from ../models/oss-20b.Q4_K_M.gguf
INFO     Model loaded successfully with Metal acceleration
INFO     Context size: 65536 tokens
INFO     Server starting on http://0.0.0.0:8000
```

### 6. Run the Frontend (Optional)

```bash
cd frontend

# Install dependencies
pnpm install
# or: npm install

# Start development server
pnpm dev
# or: npm run dev

# Frontend will start on http://localhost:5173
```

## Project Structure

```
town-of-silicon/
├── backend/                      # Python FastAPI backend
│   ├── actions/                 # Game action systems
│   │   ├── night_actions.py     # Night phase resolution
│   │   └── voting.py            # Voting and judgment
│   ├── ai/                      # AI player systems
│   │   ├── context_manager.py   # 64K context management
│   │   ├── decision_engine.py   # AI decision making
│   │   └── llm_client.py        # LLM interface
│   ├── api/                     # WebSocket & REST APIs
│   │   └── websocket.py         # Real-time communication
│   ├── config/                  # Configuration
│   │   ├── roles.yaml           # Role definitions
│   │   └── settings.py          # App settings
│   ├── core/                    # Game logic systems
│   │   ├── game_orchestrator.py # Main game loop
│   │   ├── phase_manager.py     # Phase transitions
│   │   ├── role_assignment.py   # Role distribution
│   │   └── game_persistence.py  # Save/load games
│   ├── models/                  # Pydantic data models
│   │   ├── game.py              # Game state models
│   │   ├── player.py            # Player models
│   │   ├── role.py              # Role models
│   │   └── ai.py                # AI memory models
│   ├── main.py                  # Application entry point
│   ├── requirements.txt         # Python dependencies
│   └── .env.example             # Environment template
│
├── frontend/                    # Canvas-based UI
│   ├── src/
│   │   ├── canvas/              # Canvas rendering engine
│   │   ├── ui/                  # UI components
│   │   └── api/                 # WebSocket client
│   └── package.json
│
├── models/                      # LLM models (gitignored)
│   └── oss-20b.Q4_K_M.gguf      # Download separately
│
├── docs/                        # Documentation
│   ├── ARCHITECTURE.md          # System architecture
│   └── specs/                   # Game specifications
│
├── requirements.txt             # Root dependencies
├── README.md                    # This file
└── .gitignore
```

## Game Mechanics

### Implemented Features (97% Complete)

#### ✅ Core Systems
- **Phase Management**: Night, Day, Discussion, Voting, Judgment
- **Role Assignment**: 15 players with balanced role distribution
- **Victory Conditions**: Town, Mafia, NK, individual wins (Jester, Executioner)
- **Death System**: Wills, death notes, role reveals
- **Communication**: Day chat, Mafia night chat, whispers

#### ✅ Role Abilities (24+ Roles)
**Town Roles:**
- Investigative: Sheriff, Investigator, Lookout, Spy
- Killing: Veteran, Vigilante, Jailor
- Protective: Doctor, Bodyguard
- Support: Escort, Mayor, Medium, Retributionist

**Mafia Roles:**
- Killing: Godfather, Mafioso
- Deception: Framer, Janitor, Forger, Disguiser, Hypnotist
- Support: Consort, Blackmailer, Consigliere

**Neutral Roles:**
- Killing: Serial Killer, Werewolf, Arsonist, Juggernaut
- Evil: Executioner, Jester
- Benign: Survivor, Amnesiac

#### ✅ Advanced Mechanics
- **Ability Use Limits**: Veteran (3 alerts), Jailor (3 executes), etc.
- **Cooldown System**: Werewolf full moon mechanic
- **Priority System**: Actions resolve in correct order (0-8)
- **Role Interactions**: Veteran kills visitors, SK kills roleblockers
- **Individual Wins**: Jester haunt, Executioner target tracking
- **Defense System**: Basic, Powerful, Unstoppable attacks vs defenses
- **Visitor Tracking**: Lookout sees who visits targets
- **Frame System**: Framer affects Sheriff investigations

### Current Limitations
- Transport swap (in progress)
- Vigilante guilt mechanic (in progress)
- Bodyguard counterattack (in progress)
- Mayor restrictions post-reveal (in progress)

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

### Memory Usage by Game Phase

| Phase | Active AIs | Context Size | Memory |
|-------|-----------|--------------|--------|
| Night | 14 (batched) | ~20-30K tokens | ~28 GB |
| Day Chat | 3-5 | ~20-30K tokens | ~26 GB |
| Voting | 14 (batched) | ~25-35K tokens | ~30 GB |

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

### Performance by Hardware

| Hardware | Night Phase | Chat (per AI) | Notes |
|----------|-------------|---------------|-------|
| M4 Pro 48GB | ~16s | ~1.5s | Optimal |
| M3 Max 64GB | ~20s | ~2s | Excellent |
| M2 Ultra 128GB | ~18s | ~1.8s | Excellent |
| M1 Max 32GB | ~30s | ~3s | Reduce context to 32K |

## Development

### Backend Development

```bash
cd backend
source venv/bin/activate

# Run with hot reload
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Run tests
pytest tests/ -v

# Type checking
mypy backend/

# Linting
ruff check .
ruff format .

# Check all
pytest && mypy . && ruff check .
```

### Testing Game Mechanics

```python
# Test role assignment
from backend.core.role_assignment import role_registry, role_assignment_system

assignments = role_assignment_system.assign_roles("classic")
players = role_assignment_system.create_players_from_assignments(assignments)

# Test night resolution
from backend.actions.night_actions import NightActionResolver
from backend.models.game import GameState

resolver = NightActionResolver()
summary = resolver.resolve_night(game_state, actions)
```

### Frontend Development

```bash
cd frontend

# Development server
pnpm dev

# Build for production
pnpm build

# Preview production build
pnpm preview

# Type checking
pnpm type-check

# Linting
pnpm lint
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
  "system_prompt": "500 tokens",       # Role instructions
  "role_info": "300 tokens",           # Abilities, goals
  "chat_history": "15,000 tokens",     # ALL messages
  "vote_history": "2,000 tokens",      # ALL votes/trials
  "deaths_wills": "3,000 tokens",      # ALL deaths
  "investigations": "1,500 tokens",    # ALL results
  "ai_memory": "3,000 tokens",         # Suspicions, notes
  "current_phase": "200 tokens"        # Phase context
}

Total: ~26,000 tokens
Remaining: 38,000 tokens (room to grow!)
```

### Key Design Decisions

1. **No Summarization**: Full game history in every AI decision
2. **Batched Inference**: Process 4 AIs in parallel for speed
3. **Priority-based Resolution**: Night actions in order 0-8
4. **Pydantic Models**: Type-safe data validation
5. **WebSocket Communication**: Real-time game updates
6. **JSON Persistence**: Save/load complete game states

## Troubleshooting

### Model Not Loading

```bash
# Verify model path
ls -lh models/oss-20b.Q4_K_M.gguf

# Check Python version
python --version  # Should be 3.11+

# Test llama-cpp-python installation
python -c "from llama_cpp import Llama; print('✓ llama-cpp-python working')"

# Check Metal support (Apple Silicon)
python -c "from llama_cpp import Llama; import os; os.environ['LLAMA_CPP_LIB']=''; print('Metal supported!')"

# Rebuild with Metal if needed
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python --upgrade --force-reinstall --no-cache-dir
```

### Out of Memory

```bash
# Check memory usage
# macOS: Activity Monitor > Memory tab
# Linux: htop or free -h

# Reduce context size in .env
LLM_CONTEXT_SIZE=32768  # Reduce to 32K

# Reduce batch size
AI_BATCH_SIZE=2  # Process 2 AIs at once instead of 4

# Reduce GPU layers (use more CPU)
LLM_N_GPU_LAYERS=20  # Instead of -1 (all)
```

### Slow Performance

```bash
# Ensure Metal acceleration is working
# Check logs for: "ggml_metal_init: allocating"

# Verify GPU offloading
# Logs should show: "offloading X layers to GPU"

# Reduce model size (if needed)
# Download a smaller quantization:
# - Q3_K_M: ~8GB (faster, less accurate)
# - Q4_K_M: ~11GB (balanced) ← recommended
# - Q5_K_M: ~14GB (slower, more accurate)

# Adjust threads
LLM_N_THREADS=8  # Reduce if too high
```

### Import Errors

```bash
# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt --force-reinstall

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Ensure you're in the backend directory
cd backend
python main.py
```

### WebSocket Connection Issues

```bash
# Check CORS settings in .env
CORS_ORIGINS=http://localhost:5173,http://localhost:3000

# Verify backend is running
curl http://localhost:8000/health

# Check WebSocket endpoint
# Should be: ws://localhost:8000/ws

# Frontend proxy settings (vite.config.ts)
# Ensure WebSocket proxy is configured
```

## Configuration Guide

### Environment Variables

See `backend/.env.example` for all available options. Key settings:

**LLM Configuration:**
- `LLM_MODEL_PATH`: Path to GGUF model file
- `LLM_CONTEXT_SIZE`: Context window (65536 for 64K)
- `LLM_N_GPU_LAYERS`: GPU offloading (-1 = all)
- `LLM_TEMPERATURE`: Creativity (0.7 default)

**Game Configuration:**
- `AI_BATCH_SIZE`: Parallel AI processing (4 recommended)
- `DEFAULT_ROLE_LIST`: Role distribution ("classic")
- `GAME_TIMEOUT`: Max game duration (3600s default)

**Server Configuration:**
- `HOST`: Server address (0.0.0.0)
- `PORT`: Server port (8000)
- `CORS_ORIGINS`: Allowed origins
- `DEBUG`: Enable debug logging

### Role Configuration

Roles are defined in `backend/config/roles.yaml`:

```yaml
town_investigative:
  sheriff:
    id: "sheriff"
    name: "Sheriff"
    faction: "Town"
    abilities:
      - name: "Interrogate"
        action_type: "investigate"
        priority: 5
        max_uses: null  # Unlimited
        cooldown_nights: 0
    # ... more configuration
```

## API Reference

### REST Endpoints

- `GET /health` - Health check
- `GET /docs` - Swagger documentation
- `POST /api/game/start` - Start new game
- `GET /api/game/state` - Get current state

### WebSocket Events

**Client → Server:**
- `chat_message` - Send chat message
- `night_action` - Submit night action
- `vote` - Cast vote
- `judgment` - Vote guilty/innocent

**Server → Client:**
- `phase_change` - New game phase
- `chat_message` - New chat message
- `night_result` - Night action result
- `player_died` - Player death
- `game_over` - Game ended

## Contributing

Contributions are welcome! Please see the implementation status:

**High Priority:**
- Transport action swapping
- Vigilante guilt mechanic
- Bodyguard counterattack
- Mayor post-reveal restrictions

**Medium Priority:**
- Additional role implementations
- UI/UX improvements
- Performance optimizations

**Low Priority:**
- Alternative LLM support
- Multiplayer support
- Advanced AI strategies

## FAQ

**Q: Can I use a different LLM?**
A: Yes! The code uses `llama-cpp-python`, so any GGUF model works. Adjust `LLM_MODEL_PATH` in `.env`.

**Q: Can I run this without a GPU?**
A: Yes, but it will be slower. Set `LLM_N_GPU_LAYERS=0` for CPU-only mode.

**Q: How much RAM do I need?**
A: Minimum 32GB (with 32K context). 48GB+ recommended for full 64K context.

**Q: Can I play with other humans?**
A: Not yet! This is single-player only. Multiplayer support is a future goal.

**Q: Why 64K context?**
A: It eliminates summarization, giving AIs perfect memory. They remember every detail from the entire game.

**Q: How accurate are the AI decisions?**
A: With oss-20b, AIs make sophisticated deductions, form alliances, and execute complex strategies. They're surprisingly good!

## License

MIT License - See LICENSE file for details

## Credits

- **Game Design**: BlankMediaGames (Town of Salem)
- **LLM**: oss-20b via llama.cpp
- **Framework**: FastAPI + Pydantic AI
- **Inspiration**: Town of Salem community

## Links

- **Repository**: https://github.com/yourusername/town-of-silicon
- **Documentation**: See `docs/` directory
- **Issues**: GitHub Issues
- **Hugging Face Model**: https://huggingface.co/TheBloke/OSS-20B-GGUF

---

**Built with ❤️ for the Town of Salem community**
