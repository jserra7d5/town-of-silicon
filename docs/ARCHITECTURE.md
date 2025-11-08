# Town of Salem AI - Master Architecture Document

## Project Overview

A single-player, text-based implementation of Town of Salem with 1 human player and 14 AI-controlled players powered by LLMs (Large Language Models). The game faithfully recreates the original Town of Salem mechanics while providing an engaging solo experience.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Game Client (UI)                      │
│  - React/HTML5 Frontend                                 │
│  - WebSocket Connection                                 │
│  - Local State Management                               │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              Game Server (Python)                       │
│  ┌──────────────────────────────────────────────────┐  │
│  │            Core Game Engine                      │  │
│  │  - Phase Management                              │  │
│  │  - Action Resolution                             │  │
│  │  - Victory Condition Checking                    │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │         AI Player Management                     │  │
│  │  - 14 AI Player Instances                        │  │
│  │  - Context Management (Pydantic AI)              │  │
│  │  - Decision Engine                               │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│              LLM Services                               │
│  ┌──────────────────────┐  ┌───────────────────────┐   │
│  │   Local LLM          │  │  OpenRouter API       │   │
│  │  (via Groq/Ollama)   │  │  (Remote)             │   │
│  │  - OSS-20B+ models   │  │  - GPT-4, Claude, etc.│   │
│  └──────────────────────┘  └───────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend:**
- Language: Python 3.11+
- Framework: FastAPI or similar
- AI Framework: Pydantic AI
- Data Validation: Pydantic v2
- LLM Integration:
  - Local: Groq API or Ollama
  - Remote: OpenRouter API

**Frontend:**
- Framework: React or vanilla HTML5/JavaScript
- Communication: WebSockets (real-time)
- State: React Context or Redux
- Styling: CSS3, responsive design

**LLM Models:**
- Local: Llama 3.1 70B, Mixtral 8x7B, or similar (20B+ parameters)
- Remote: GPT-4, Claude 3.5, Gemini Pro (via OpenRouter)

## System Components

### 1. Core Systems

#### 1.1 Role Assignment System
- **File:** `docs/specs/core/role_assignment_system_spec.txt`
- **Responsibilities:**
  - Assign 15 roles at game start
  - Enforce role list constraints (Classic, Ranked, Custom)
  - Handle unique role limits
  - Validate faction balance

#### 1.2 Phase Management System
- **File:** `docs/specs/core/phase_management_system_spec.txt`
- **Responsibilities:**
  - Manage game phases (Day, Night, Trial, Judgment)
  - Handle phase transitions
  - Maintain game clock and timers
  - Allow AI time extensions (for LLM processing)

#### 1.3 Victory Condition System
- **File:** `docs/specs/core/victory_condition_system_spec.txt`
- **Responsibilities:**
  - Check victory conditions (Town, Mafia, NK, Neutral)
  - Handle simultaneous wins (Survivor, Witch)
  - End game when victory achieved
  - Generate victory screen

#### 1.4 Death System
- **File:** `docs/specs/core/death_system_spec.txt`
- **Responsibilities:**
  - Process player deaths
  - Display death announcements
  - Reveal roles on death
  - Manage graveyard and graveyard chat

### 2. Communication Systems

#### 2.1 Day Chat System
- **File:** `docs/specs/communication/day_chat_system_spec.txt`
- **Responsibilities:**
  - Public day chat (all living players)
  - Message validation and rate limiting
  - Blackmail effect (prevent speaking)
  - Typing indicators

#### 2.2 Whisper System
- **File:** `docs/specs/communication/whisper_system_spec.txt`
- **Responsibilities:**
  - Private 1-on-1 messaging
  - Blackmailer interception (sees all whispers)
  - Public whisper notifications
  - Mayor whisper restriction

#### 2.3 Last Will System
- **File:** `docs/specs/communication/last_will_system_spec.txt`
- **Responsibilities:**
  - Will editing (200 char limit)
  - Will display on death
  - Forger ability (replace wills)
  - Will templates

#### 2.4 Death Note System
- **File:** `docs/specs/communication/death_note_system_spec.txt`
- **Responsibilities:**
  - Killers leave notes on victims
  - Death note display (100 char limit)
  - Strategic deception
  - Janitor interaction (hides notes)

### 3. Action Systems

#### 3.1 Night Action System
- **File:** `docs/specs/action/night_action_system_spec.txt`
- **Responsibilities:**
  - Collect night actions from all players
  - Resolve actions in priority order
  - Handle roleblocks, redirects, kills, protection
  - Generate action results

**Priority Order:**
1. Priority 0: Defensive setup (Veteran alert, Bodyguard)
2. Priority 1: Redirects (Witch control, Transporter swap)
3. Priority 2: Roleblocks (Escort, Consort)
4. Priority 3: Protection (Doctor, Jail)
5. Priority 4: Investigation (Sheriff, Investigator, Lookout)
6. Priority 5: Kills (Mafia, SK, Vigilante)
7. Priority 6: Arsonist (douse/ignite)
8. Priority 7: Manipulation (Janitor clean, Forger forge)
9. Priority 8: Blackmail

#### 3.2 Voting System
- **File:** `docs/specs/action/voting_system_spec.txt`
- **Responsibilities:**
  - Accusation voting (majority needed)
  - Trial phases (Defense, Judgment)
  - Judgment voting (Guilty/Innocent/Abstain)
  - Mayor vote weight (3 votes)

#### 3.3 Role Ability System
- **File:** `docs/specs/action/role_ability_system_spec.txt`
- **Responsibilities:**
  - Define all role abilities
  - Track ability uses (limited abilities)
  - Validate ability usage
  - Apply cooldowns

### 4. Information Systems

#### 4.1 Investigation Result System
- **File:** `docs/specs/information/investigation_result_system_spec.txt`
- **Responsibilities:**
  - Generate investigation results
  - Handle Framer (fake suspicious results)
  - Handle Disguiser (fake role reveals)
  - Deliver results to investigators

**Investigation Types:**
- Sheriff: Suspicious / Not Suspicious
- Investigator: Set of 3 possible roles
- Lookout: List of visitors
- Consigliere: Exact role

#### 4.2 Notification System
- **File:** `docs/specs/information/notification_system_spec.txt`
- **Responsibilities:**
  - Death announcements
  - Investigation results
  - Action feedback (attacked, healed, etc.)
  - Phase change notifications

#### 4.3 Player List Display
- **File:** `docs/specs/information/player_list_display_spec.txt`
- **Responsibilities:**
  - Display all 15 players
  - Show status (alive/dead)
  - Show revealed roles
  - Vote counters

### 5. AI-Specific Systems

#### 5.1 AI Context Management
- **File:** `docs/specs/ai/ai_context_management_spec.txt`
- **Responsibilities:**
  - Manage context window for each AI (Pydantic AI)
  - Information isolation (AIs only know what they should)
  - Context summarization (prevent token overflow)
  - LLM provider configuration (local/OpenRouter)

**Context Structure:**
```python
AIContext:
  - role: str
  - faction: str
  - known_information: (investigations, revealed roles, etc.)
  - memory: (suspicions, claims, observations)
  - chat_history: (recent messages)
```

#### 5.2 AI Decision Engine
- **File:** `docs/specs/ai/ai_decision_engine_spec.txt`
- **Responsibilities:**
  - Night target selection
  - Voting decisions
  - Role claim decisions
  - Defense speech generation

**Decision Flow:**
1. Build LLM prompt with context
2. Call LLM via Pydantic AI
3. Parse structured response
4. Validate decision
5. Execute action
6. Fallback to rules if LLM fails

#### 5.3 AI Communication Generator
- **File:** `docs/specs/ai/ai_communication_generator_spec.txt`
- **Responsibilities:**
  - Generate day chat messages
  - Generate whispers
  - Generate defense speeches
  - Simulate typing delays

**Message Generation:**
- Prompt LLM with context and purpose
- Generate natural, in-character messages
- Enforce character limits (200 chars)
- Vary tone by role/faction

#### 5.4 AI Memory System
- **File:** `docs/specs/ai/ai_memory_system_spec.txt`
- **Responsibilities:**
  - Track suspicion levels (0.0-1.0 per player)
  - Record role claims
  - Store behavioral observations
  - Analyze voting patterns

**Memory Operations:**
- Update suspicion (based on events)
- Record claims (track contradictions)
- Consolidate memory (summarize old data)
- Retrieve top suspects

### 6. Player Interface Systems

#### 6.1 Action Selection UI
- **File:** `docs/specs/interface/action_selection_ui_spec.txt`
- **Responsibilities:**
  - Night action panel (target selection)
  - Day voting UI
  - Judgment voting UI
  - Action confirmation

#### 6.2 Information Display UI
- **File:** `docs/specs/interface/information_display_ui_spec.txt`
- **Responsibilities:**
  - Role card display
  - Player list UI
  - Chat log UI
  - Graveyard panel
  - Notification modals

#### 6.3 Game Settings
- **File:** `docs/specs/interface/game_settings_spec.txt`
- **Responsibilities:**
  - Game mode selection (Classic, Ranked, Custom)
  - Timing configuration
  - AI/LLM configuration
  - UI preferences
  - Custom role list editor

## Data Flow

### Game Initialization Flow

```
1. User selects settings (mode, role list, position)
2. Role Assignment System assigns 15 roles
3. AI Context Management initializes 14 AI contexts
4. Phase Management starts with Night 1
5. UI displays role card to human player
```

### Night Phase Flow

```
1. Phase Management: Transition to NIGHT
2. Night Action System: Request actions from all players
3. Human Player: Select target via UI
4. AI Players (14x in parallel):
   a. AI Decision Engine: Determine target
   b. LLM call via Pydantic AI (with timeout)
   c. Submit action to Night Action System
5. When all actions submitted OR timer expires:
   a. Sort actions by priority
   b. Resolve each action sequentially
   c. Generate results (deaths, investigations, etc.)
6. Phase Management: Transition to DAY
7. Display death announcements and results
```

### Day Phase Flow

```
1. Phase Management: Transition to DAY_DISCUSSION
2. Death System: Display death announcements
3. Notification System: Deliver investigation results
4. Chat enabled:
   a. Human types messages in UI
   b. AI Communication Generator: Generate messages for AIs
   c. All messages broadcast via Day Chat System
5. Voting:
   a. Players vote to accuse someone
   b. If majority reached: Transition to DEFENSE
   c. Defense speech (20s)
   d. Judgment voting (Guilty/Innocent/Abstain)
   e. If Guilty: Execute and transition to NIGHT
   f. If Innocent: Return to DAY_DISCUSSION
6. If no successful lynch: Transition to NIGHT
```

### AI Decision-Making Flow (Night Target Example)

```
1. Night Action System requests target from AI Player #3
2. AI Context Manager builds context:
   - Role: Mafia Godfather
   - Faction: Mafia
   - Known: Other Mafia members
   - Suspicions: Player 7 (0.8), Player 12 (0.6)
   - Recent events: Player 5 claimed Sheriff
3. AI Decision Engine builds prompt:
   "You are Godfather. Choose kill target. Options: ..."
4. Pydantic AI Agent calls LLM:
   - Provider: local (Groq) or OpenRouter
   - Model: llama-3.1-70b or gpt-4
   - Timeout: 20 seconds
5. LLM responds: {"target_id": 5, "reasoning": "Sheriff is threat"}
6. Validate target (Player 5 is alive? Yes)
7. Submit action: Kill Player 5
8. If LLM times out: Use fallback (random high-suspicion target)
```

## Pydantic AI Integration

### Context Window Management

Pydantic AI automatically manages the context window for each AI player:

```python
from pydantic_ai import Agent
from pydantic import BaseModel

class TargetDecision(BaseModel):
    target_id: int
    reasoning: str

# Create agent for AI player
agent = Agent(
    model='openai:gpt-4o',  # or 'groq:llama-3.1-70b'
    result_type=TargetDecision,
    system_prompt=build_system_prompt(ai_context)
)

# Run with automatic context management
result = await agent.run(
    user_prompt="Choose your target for tonight",
    deps=ai_context,  # AIContext object
    timeout=20.0
)

# result.data is validated TargetDecision
target_id = result.data.target_id
```

### LLM Provider Configuration

**Local LLM (Groq/Ollama):**
```python
llm_config = {
    "provider": "local",
    "endpoint": "http://localhost:11434/v1/chat/completions",
    "model": "llama-3.1-70b",
    "max_tokens": 8192,
    "timeout": 30
}
```

**OpenRouter (Remote):**
```python
llm_config = {
    "provider": "openrouter",
    "api_key": os.getenv("OPENROUTER_API_KEY"),
    "model": "anthropic/claude-3.5-sonnet",
    "max_tokens": 8192,
    "timeout": 30
}
```

### Context Summarization

To fit within token limits:
- Keep recent messages (last 50) in full
- Summarize older messages using LLM
- Always include: role info, faction members, investigations, revealed roles
- Progressive summarization as game progresses

## Performance Considerations

### Timing Budget

**Night Phase:**
- Action collection: 30 seconds (base, extendable)
- AI decision-making: 2-15 seconds per AI (parallel)
- Action resolution: <500ms
- Total: ~30-60 seconds

**Day Phase:**
- Chat generation: 2-10 seconds per message
- Typing simulation: 3-15 seconds
- Decision-making (voting): 1-5 seconds
- Realistic human-like timing

### Concurrency

- All 14 AI players make decisions in parallel
- Use asyncio for concurrent LLM calls
- Timeout individual AIs (don't block on slow LLM)
- Fallback to rule-based if AI times out

### Optimization

- Cache role definitions and configurations
- Reuse LLM connections (connection pooling)
- Lazy load chat history (paginate old messages)
- Virtual scrolling in UI for long lists

## Edge Cases and Error Handling

### LLM Failures

**Timeout:**
- Individual AI timeout: 20-30 seconds
- Use fallback decision (rule-based)
- Log error for debugging

**Invalid Response:**
- LLM returns malformed JSON
- Parse error → use fallback
- Validate all decisions before execution

**Connection Failure:**
- Retry once with exponential backoff
- If still fails: fallback decision
- Show warning to user

### Game State Issues

**All Players Dead Simultaneously:**
- Check victory conditions
- Result: Draw (everyone died)
- Display appropriate end screen

**Phase Transition During Action:**
- Server is authoritative
- Client displays "Phase ended"
- Discard incomplete actions

**Disconnection/Reconnection:**
- Save game state server-side
- Reconnect: Restore state
- Auto-play for disconnected human (abstain, no action)

## Testing Strategy

### Unit Tests
- Each system component tested independently
- Mock dependencies
- Test edge cases (all roles, all phases)

### Integration Tests
- Full game simulations
- Test victory conditions (Town win, Mafia win, NK win)
- Test all role interactions

### AI Tests
- Test AI decision-making with various contexts
- Validate context window management
- Test fallback behavior

### Performance Tests
- 15 concurrent AI LLM calls
- Phase transition timing
- Memory usage over long game

## Deployment

### Local Development
```bash
# Backend
cd backend
pip install -r requirements.txt
python main.py

# Frontend
cd frontend
npm install
npm run dev
```

### Docker Deployment
```dockerfile
# Backend container
FROM python:3.11
COPY backend /app
RUN pip install -r requirements.txt
CMD ["python", "main.py"]

# Frontend container (if separate)
FROM node:18
COPY frontend /app
RUN npm install && npm run build
CMD ["npm", "start"]
```

### Environment Variables
```
OPENROUTER_API_KEY=sk-...
LOCAL_LLM_ENDPOINT=http://localhost:11434
LOG_LEVEL=INFO
```

## Future Enhancements

### Potential Features
- Multiplayer mode (1 human + 14 AI → multiple humans + AI)
- Replay system (watch games after completion)
- AI personality customization
- More role lists (Coven expansion, custom roles)
- Statistics and analytics (win rates, best plays)
- Voice narration (TTS for game events)

### Performance Improvements
- GPU acceleration for local LLMs
- Caching of common AI decisions
- Optimized prompt templates
- Streaming LLM responses

## Conclusion

This architecture provides a robust, scalable foundation for a single-player Town of Salem experience powered by AI agents. The modular design allows for easy testing, maintenance, and future enhancements. The use of Pydantic AI ensures type-safe, validated interactions with LLMs while managing context windows effectively.

All 21 specification files provide detailed implementation guidance for each subsystem, ensuring a comprehensive and high-quality implementation.

---

**Total Specifications:** 21 files
- Core Systems: 4
- Communication Systems: 4
- Action Systems: 3
- Information Systems: 3
- AI-Specific Systems: 4
- Player Interface Systems: 3

**Estimated Implementation Time:** 3-6 months (single developer)

**Technology Maturity:** Production-ready with existing libraries (Pydantic AI, FastAPI, React)
