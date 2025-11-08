# Project Issues and Gaps Analysis

**Generated:** 2025-11-08
**Status:** Critical issues found that will prevent the game from running

---

## 🔴 **CRITICAL ISSUES** (Blocks execution)

### 1. Missing `__init__.py` Files
**Impact:** Python cannot import any modules - nothing will work

**Missing in:**
- `backend/`
- `backend/core/`
- `backend/ai/`
- `backend/actions/`
- `backend/api/`
- `backend/models/`
- `backend/config/`
- `frontend/src/`
- `frontend/src/api/`
- `frontend/src/canvas/`

**Fix Required:**
```bash
touch backend/__init__.py
touch backend/core/__init__.py
touch backend/ai/__init__.py
touch backend/actions/__init__.py
touch backend/api/__init__.py
touch backend/models/__init__.py
touch backend/config/__init__.py
```

---

### 2. Data Model Mismatches (Critical)

#### ChatMessage Model Mismatch
**Location:** `backend/models/game.py` vs usage in `backend/core/game_orchestrator.py`

**Model Definition:**
```python
class ChatMessage(BaseModel):
    message_id: int              # REQUIRED but never set!
    sender_id: int               # orchestrator uses player_id
    sender_name: str             # orchestrator uses player_name
    content: str                 # orchestrator uses message
    timestamp: datetime
    day_number: int
    is_whisper: bool = False
    whisper_to: int | None = None
```

**Orchestrator Usage:**
```python
ChatMessage(
    player_id=player.player_id,      # FIELD DOESN'T EXIST
    player_name=player.name,         # FIELD DOESN'T EXIST
    message=decision.message,        # FIELD DOESN'T EXIST
    phase=PhaseType.DAY_DISCUSSION.value,  # FIELD DOESN'T EXIST
    day_number=self.game_state.current_day
)
```

**Result:** Will crash with Pydantic validation error on first chat message

---

#### DeathInfo Model Mismatch
**Location:** `backend/models/player.py` vs usage in orchestrator

**Model Definition:**
```python
class DeathInfo(BaseModel):
    player_id: int
    player_name: str      # REQUIRED but not set
    role: str             # REQUIRED but not set
    faction: str          # REQUIRED but not set
    night: int = 0        # orchestrator uses day_number
    day: int = 0
    cause: str
    killed_by: int | None = None
    last_will: str        # REQUIRED but not set
    death_note: str | None = None
    cleaned: bool = False
    timestamp: datetime
```

**Orchestrator Usage:**
```python
DeathInfo(
    player_id=accused_id,
    day_number=self.game_state.current_day,  # FIELD DOESN'T EXIST
    phase="Day",                              # FIELD DOESN'T EXIST
    cause="Lynched",
    role_revealed=accused.role.name           # FIELD DOESN'T EXIST
)
```

**Result:** Will crash with Pydantic validation error on first death

---

#### Player Model Has Duplicate death_info Field
**Location:** `backend/models/player.py`

```python
class Player(BaseModel):
    # Old death tracking (unused)
    death_night: int = 0
    death_day: int = 0
    death_cause: str | None = None

    # But orchestrator expects:
    death_info: DeathInfo | None = None  # FIELD DOESN'T EXIST IN MODEL
```

**Result:** Orchestrator sets `player.death_info` but field doesn't exist

---

#### GameState Missing Fields
**Location:** `backend/models/game.py`

```python
class GameState(BaseModel):
    # ... existing fields ...

    # MISSING FIELD used by orchestrator:
    last_judgment_result: JudgmentResult | None = None  # DOESN'T EXIST
```

**Result:** Will crash when trying to set `game_state.last_judgment_result`

---

### 3. Import Errors

#### PlayerRoleAssignment Import Error
**Location:** `backend/core/role_assignment.py:10`

```python
from ..models.role import (
    Role, RoleList, RoleSlot, RoleConstraint, RoleAbility,
    FactionType, AttackValue, DefenseValue, PlayerRoleAssignment  # NOT IN role.py
)
```

**Actual Location:** `backend/models/player.py:38`

**Fix:** Import from correct module

---

#### GameState Missing game_id
**Location:** `backend/core/game_orchestrator.py:185`

```python
self.game_state = GameState(
    players=players,
    current_phase=GamePhase(...),
    current_day=0
    # MISSING: game_id (required field in model!)
)
```

**Result:** Will crash with Pydantic validation error

---

## 🟡 **MAJOR GAPS** (Missing features from specs)

### 4. Communication Systems (0% implemented)

**Specified but completely missing:**

- ❌ **Whisper System** (`backend/communication/whisper.py`)
  - Spec: `docs/specs/communication/whisper_system_spec.txt`
  - Status: Not implemented
  - Impact: Players cannot whisper (core mechanic)

- ❌ **Last Will System** (`backend/communication/last_will.py`)
  - Spec: `docs/specs/communication/last_will_system_spec.txt`
  - Status: Not implemented
  - Impact: Dead players can't leave wills (core mechanic)

- ❌ **Death Note System** (`backend/communication/death_note.py`)
  - Spec: `docs/specs/communication/death_note_system_spec.txt`
  - Status: Not implemented
  - Impact: Killers can't leave death notes (core mechanic)

---

### 5. Half-Implemented Night Actions

**Location:** `backend/actions/night_actions.py`

```python
def _handle_investigate(self, ...):
    # TODO: Check if target is framed  (line 262)
    # Missing framing status tracking

def _get_lookout_result(self, ...):
    # TODO: Track visitors in resolution  (line 482)
    # Returns "No one visited" always - broken
```

**Missing:**
- Framer tracking (Framer can frame players but has no effect)
- Visitor tracking for Lookout (Lookout gets no real results)
- Janitor cleaning (cleaned bodies not tracked)
- Transporter redirection (transport does nothing)

---

### 6. Half-Implemented Voting System

**Location:** `backend/actions/voting.py`

```python
def can_vote(self, ...):
    # TODO: Check blackmail status  (line 228)
    # Blackmailer blocks votes but not implemented

def reveal_mayor(self, ...):
    # TODO: Add revealed status to player  (line 253)
    # Mayor can reveal but status not tracked

def _get_vote_weight(self, ...):
    # TODO: Check if mayor is revealed  (line 292)
    # Mayor always has 1 vote (should be 3 when revealed)

def _is_blackmailed(self, ...):
    # TODO: Implement blackmail tracking  (line 301)
    return False  # Stub - always returns False
```

**Impact:**
- Blackmailer role doesn't work
- Mayor reveal doesn't work
- Mayor vote weight is wrong

---

### 7. Missing AI Features

**Location:** `backend/ai/llm_client.py:183`

```python
async def batch_generate_structured(self, ...):
    # TODO: Implement actual batching with multiple model instances
    # Currently falls back to sequential processing
    # Performance impact: 14 AIs take 28-140s instead of 2-10s
```

**Impact:** No true parallel AI processing - game will be very slow

---

### 8. Missing Frontend Components

**Missing from original design:**

```typescript
// Specified in Game.ts:23-26 but not implemented:
import { ChatRenderer } from './ChatRenderer';     // DOESN'T EXIST
import { ButtonPanel } from './ButtonPanel';       // DOESN'T EXIST
import { PhaseIndicator } from './PhaseIndicator'; // DOESN'T EXIST
```

**Current State:**
- Basic canvas rendering exists
- No chat input UI
- No action buttons
- No interactive elements for human player

**Result:** Human cannot play - display only mode

---

## 🟠 **MODERATE ISSUES** (Partially working)

### 9. Incomplete Role Definitions

**Location:** `backend/config/roles.yaml`

**Issues:**
- Only 21 roles defined (should be 40+)
- Missing roles:
  - Veteran
  - Transporter
  - Disguiser
  - Consigliere
  - Consort
  - Werewolf
  - Executioner
  - Witch
  - Amnesiac
  - And 15+ more...

**Impact:** "Classic" role list may assign undefined roles

---

### 10. Phase Manager Has Placeholder Human Action Handling

**Location:** `backend/core/game_orchestrator.py:256`

```python
# Wait for human action if alive
human = self.game_state.players[self.human_player_id]
if human.is_alive and human.role.abilities:
    # Wait for human to submit action via WebSocket
    # For now, skip human action (would come from ws_handler.action_queue)
    pass  # ← HUMAN CANNOT ACT
```

**Result:** Human player watches but cannot interact

---

### 11. Missing Investigation Result System

**No tracking for:**
- Sheriff results (who is Mafia/SK)
- Investigator results (role groups)
- Lookout results (who visited)
- Spy results (Mafia visits/whispers)

**Impact:** Investigation abilities work but results aren't stored for AI memory

---

### 12. No Victory Condition Checks During Game

**Location:** `backend/core/game_orchestrator.py:490`

```python
def check_victory(self) -> Optional[str]:
    # Only checks basic Town vs Mafia
    # Missing:
    # - Jester win (get lynched)
    # - Executioner win (target lynched)
    # - Serial Killer solo win
    # - Arsonist solo win
    # - Survivor win condition
```

---

## 🟢 **MINOR ISSUES** (Polish/edge cases)

### 13. Missing Error Handling

- No try/except in game loop
- No reconnection for dropped WebSocket clients
- No validation of human actions
- No timeout handling for stuck phases

### 14. No Persistence

- Game state not saved
- Cannot resume games
- No replay/history export
- No game logs

### 15. Missing Mafia Chat

**Specified:** Mafia should have private night chat
**Status:** WebSocket handler has `broadcast_to_mafia()` but never used
**Impact:** Mafia cannot coordinate

### 16. No Settings/Configuration UI

- Cannot adjust phase timers
- Cannot select different role lists
- Cannot configure AI difficulty
- Cannot enable/disable roles

---

## 📊 **COMPLETION SUMMARY**

### Core Systems
- ✅ Role Assignment: **90%** (missing some role definitions)
- ✅ Phase Management: **95%** (complete)
- ⚠️ Victory Conditions: **60%** (basic only)
- ⚠️ Death System: **70%** (model mismatch)

### Communication Systems
- ❌ Day Chat: **40%** (model mismatch, no input UI)
- ❌ Whisper: **0%** (not implemented)
- ❌ Last Will: **0%** (not implemented)
- ❌ Death Note: **0%** (not implemented)

### Action Systems
- ⚠️ Night Actions: **70%** (missing framing, lookout tracking)
- ⚠️ Voting: **75%** (missing blackmail, mayor reveal)
- ✅ Role Abilities: **85%** (most work, some TODOs)

### Information Systems
- ⚠️ Investigation Results: **50%** (work but not tracked)
- ❌ Notifications: **0%** (not implemented)
- ✅ Player List: **90%** (display works)

### AI Systems
- ✅ Context Management: **100%** (complete)
- ✅ Decision Engine: **95%** (complete, needs testing)
- ⚠️ Communication Generator: **60%** (basic chat only)
- ✅ Memory: **100%** (64K context works)

### Player Interface
- ❌ Action Selection UI: **20%** (display only, no input)
- ✅ Information Display: **80%** (canvas rendering works)
- ❌ Game Settings: **0%** (not implemented)

---

## 🔧 **RECOMMENDED FIX ORDER**

### Phase 1: Make it Run (Critical)
1. Add all `__init__.py` files
2. Fix ChatMessage model/usage mismatch
3. Fix DeathInfo model/usage mismatch
4. Fix GameState missing fields
5. Fix import errors

### Phase 2: Make it Playable (High Priority)
6. Add chat input UI for human player
7. Add action buttons for human player
8. Implement human action handling in orchestrator
9. Fix mayor reveal/vote weight
10. Add whisper system

### Phase 3: Complete Core Mechanics (Medium Priority)
11. Implement last will system
12. Add death notes
13. Fix framer/lookout tracking
14. Complete role definitions
15. Add all victory conditions

### Phase 4: Polish (Low Priority)
16. Error handling and recovery
17. Game state persistence
18. Settings UI
19. Mafia private chat
20. AI communication variety

---

## 📝 **ESTIMATED WORK**

- **Phase 1 (Critical):** 4-6 hours
- **Phase 2 (Playable):** 8-12 hours
- **Phase 3 (Complete):** 12-16 hours
- **Phase 4 (Polish):** 8-12 hours

**Total:** 32-46 hours to full completion

**Current Completion:** ~45% (infrastructure done, features half-implemented)
