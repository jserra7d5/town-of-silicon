# Remaining Gaps After Role Ability Implementation

**Generated:** 2025-11-09
**Status:** Role abilities 95% complete, but gaps remain in mechanics and polish

---

## 🔴 HIGH-PRIORITY GAPS

### 1. **Jester Haunt Ability** (Impact: High)
**File:** `backend/core/game_orchestrator.py:769`

**Current State:**
```python
# Jester can choose to kill someone who voted guilty (not implemented yet)
```

**What's Missing:**
- Jester wins when lynched ✅ (implemented)
- Jester should be able to KILL one player who voted guilty ❌ (not implemented)
- Needs UI for haunt target selection
- Needs post-lynch phase for haunt

**Implementation Needed:**
1. Track guilty voters during judgment
2. Add haunt target selection after Jester is lynched
3. Night action for Jester haunt (Unstoppable attack)
4. UI for dead Jester to select victim

**Estimated Time:** 6-8 hours

---

### 2. **Executioner Target Tracking** (Impact: High)
**File:** `backend/core/game_orchestrator.py:775`

**Current State:**
```python
# Executioner target is stored in role metadata (not implemented in current model)
# For now, we'll skip this - would need to add target tracking to Player model
pass
```

**What's Missing:**
- Executioner role has no target assigned
- No win condition check when target is lynched
- Target should be randomly assigned at game start

**Implementation Needed:**
1. Add `executioner_target: Optional[int]` to Player model
2. Assign random non-Mafia target during role assignment
3. Check if target was lynched in `check_individual_wins()`
4. Award Executioner win when target is lynched

**Estimated Time:** 4-6 hours

---

### 3. **Transport Doesn't Actually Swap** (Impact: High)
**File:** `backend/actions/night_actions.py:287-310`

**Current State:**
```python
def _handle_transport(self, ...):
    # Transport needs two targets (stored in ability metadata)
    # For now, simplified: target_id is first, second target from action
    target1 = action.target_id
    # In full implementation, would get second target from action
    # For now, just record the transport
```

**What's Missing:**
- Only gets ONE target, needs TWO
- Doesn't actually swap/redirect actions
- `transported_pairs` is populated but never used

**Implementation Needed:**
1. Modify action collection to get TWO targets for Transporter
2. Update `_resolve_transport()` to actually redirect targets
3. Apply swaps before processing other actions
4. Update WebSocket protocol for dual-target selection

**Estimated Time:** 6-8 hours

---

### 4. **Ability Use Limits Not Enforced** (Impact: Medium)
**File:** All ability handlers

**Current State:**
- Roles.yaml defines `max_uses` for many abilities
- Player model has `ability_uses_remaining` field
- But uses are NEVER tracked or enforced

**Examples:**
- Veteran Alert: max_uses = 3 ✅ (defined) ❌ (not enforced)
- Jailor Execute: max_uses = 3 ✅ (defined) ❌ (not enforced)
- Survivor Vest: max_uses = 4 ✅ (defined) ❌ (not enforced)

**Implementation Needed:**
1. Initialize `ability_uses_remaining` when assigning roles
2. Check remaining uses before allowing action
3. Decrement uses after successful action
4. Show uses remaining to player

**Estimated Time:** 4-6 hours

---

### 5. **Cooldown System Not Implemented** (Impact: Medium)
**File:** All ability handlers

**Current State:**
- Roles.yaml defines `cooldown_nights` for abilities
- Werewolf has `cooldown_nights: 1` (every other night)
- But cooldowns are NEVER tracked

**Implementation Needed:**
1. Track `last_used_night` for each ability
2. Check cooldown before allowing action
3. Block ability use during cooldown
4. Display cooldown status to player

**Estimated Time:** 3-4 hours

---

## 🟡 MEDIUM-PRIORITY GAPS

### 6. **Vigilante Guilt Mechanic Missing** (Impact: Medium)
**File:** Roles.yaml says "die if shoot Town" but not implemented

**Current State:**
- Vigilante can shoot (implemented)
- Should die of guilt if shoots Town member ❌

**Implementation Needed:**
1. Check victim's faction after kill
2. If Town, kill Vigilante from guilt
3. Add special death cause "Guilt"

**Estimated Time:** 2-3 hours

---

### 7. **Mayor Post-Reveal Restrictions** (Impact: Low)
**File:** `backend/communication/whisper.py`, `backend/actions/night_actions.py`

**Town of Salem Rules:**
- Mayor cannot whisper after revealing
- Mayor cannot be healed by Doctor after revealing

**Current State:**
- Mayor can reveal ✅
- Gets 3 votes ✅
- But no restrictions on whispers or healing ❌

**Implementation Needed:**
1. Check `player.revealed and player.role.id == "mayor"` in whisper system
2. Block whispers from/to revealed Mayor
3. Block Doctor heal on revealed Mayor

**Estimated Time:** 2 hours

---

### 8. **Godfather/Mafioso Kill Coordination** (Impact: Medium)
**File:** `backend/actions/night_actions.py`

**Town of Salem Rules:**
- If Godfather is alive, Mafioso doesn't kill
- If Godfather dies, Mafioso becomes new killer

**Current State:**
- Both can submit kill actions
- No coordination or priority

**Implementation Needed:**
1. Check if Godfather is alive before processing Mafioso kill
2. Block Mafioso kill if Godfather is active
3. Only allow one Mafia kill per night

**Estimated Time:** 2-3 hours

---

### 9. **Bodyguard Counterattack Not Implemented** (Impact: Medium)
**File:** `backend/actions/night_actions.py:641`

**Current State:**
```python
def _handle_guard(self, ...):
    # Give target powerful defense
    self.summary.protected_players.add(target_id)
    # Note: Counterattack will be handled in post-processing
    # when we know who attacked the target
```

**What's Missing:**
- Bodyguard protects target ✅
- But doesn't kill ONE attacker ❌
- Bodyguard should die after successful guard ❌

**Implementation Needed:**
1. Post-processing after all actions resolve
2. Find who attacked the guarded player
3. Kill ONE attacker with Powerful attack
4. Kill Bodyguard after successful protection

**Estimated Time:** 4-5 hours

---

### 10. **Witch Control Needs Dual-Target UI** (Impact: Medium)
**File:** `backend/actions/night_actions.py:632`

**Current State:**
```python
def _handle_control(self, ...):
    # Witch needs two targets: controlled player and new target
    # This is complex - requires UI to select two targets
    # For now, simplified implementation
    logger.warning("Witch control not fully implemented - requires dual target selection")
```

**Implementation Needed:**
1. UI to select TWO targets (controlled + redirect target)
2. Redirect controlled player's action to new target
3. Different from Transport (which swaps positions)

**Estimated Time:** 6-8 hours

---

### 11. **Forger Will Replacement** (Impact: Low)
**File:** `backend/actions/night_actions.py:752`

**Current State:**
- Forger can target someone
- But doesn't have fake will text input
- Doesn't actually replace will

**Implementation Needed:**
1. UI for Forger to write fake will
2. Store fake will in action
3. Replace target's will if they die
4. Max 3 uses tracking

**Estimated Time:** 3-4 hours

---

### 12. **Disguiser Role Swap on Death** (Impact: Low)
**File:** `backend/actions/night_actions.py:730`

**Current State:**
- Disguiser targets someone
- But doesn't swap roles if target dies

**Implementation Needed:**
1. Post-processing after deaths
2. If target died, swap Disguiser's displayed role
3. Investigations show fake role
4. Max 3 uses tracking

**Estimated Time:** 4-5 hours

---

### 13. **Hypnotist False Information** (Impact: Low)
**File:** `backend/actions/night_actions.py:744`

**Current State:**
- Hypnotist can target someone
- But doesn't give them false information

**Implementation Needed:**
1. Generate fake investigation results
2. Send fake results to hypnotized player
3. Different from real results

**Estimated Time:** 3-4 hours

---

### 14. **Consort Basic Defense** (Impact: Low)
**File:** `backend/config/roles.yaml:407`

**Roles.yaml says:**
```yaml
consort:
  defense: 1  # Basic
```

**But Player model uses role.defense from Role, so should work ✅**

**Verification Needed:** Test that Consort has basic defense

---

### 15. **Cleaned Bodies Don't Hide Role/Will** (Impact: Low)
**File:** Death announcements

**Current State:**
- Janitor can clean ✅
- Death is marked as `cleaned: True` ✅
- But death announcements still show role ❌

**Implementation Needed:**
1. Check `death.cleaned` in death announcements
2. Hide role if cleaned ("Role: ???")
3. Hide will if cleaned

**Estimated Time:** 1-2 hours

---

## 🟢 LOW-PRIORITY POLISH GAPS

### 16. **No Multi-Ability Selection UI**
Roles with multiple abilities (Arsonist, Jailor) need UI to choose which ability to use.

**Estimated Time:** 4-6 hours

---

### 17. **No Ability Cooldown Display**
Players don't see how many uses remain or when cooldown expires.

**Estimated Time:** 2-3 hours

---

### 18. **No Vote History Display**
Can't see who voted for whom during trials.

**Estimated Time:** 3-4 hours

---

### 19. **No Investigation Results Log**
Investigative roles can't review past results.

**Estimated Time:** 3-4 hours

---

### 20. **Blackmailer Can't Read Whispers**
Roles.yaml says Blackmailer "reads all whispers" but not implemented.

**Estimated Time:** 2-3 hours

---

## 📊 SUMMARY

### Critical Gaps (Block Full Parity):
1. Jester Haunt (6-8h)
2. Executioner Target (4-6h)
3. Transport Swap (6-8h)
4. Ability Use Limits (4-6h)
5. Cooldown System (3-4h)

**Total Critical:** 23-32 hours

### Medium-Priority Gaps:
6. Vigilante Guilt (2-3h)
7. Mayor Restrictions (2h)
8. Godfather/Mafioso (2-3h)
9. Bodyguard Counterattack (4-5h)
10. Witch Control (6-8h)
11. Forger (3-4h)
12. Disguiser (4-5h)
13. Hypnotist (3-4h)
15. Cleaned Bodies (1-2h)

**Total Medium:** 27-36 hours

### Low-Priority Polish:
16-20. UI and Display (14-20h)

**Grand Total:** 64-88 hours for 100% completion

---

## ✅ WHAT'S COMPLETE

- ✅ All 24+ role abilities IMPLEMENTED (95%)
- ✅ Attack vs Defense system
- ✅ Visitor tracking (Lookout, Spy)
- ✅ Framing system
- ✅ Blackmail system (except whisper reading)
- ✅ Roleblock immunities
- ✅ Serial Killer kills roleblockers
- ✅ Veteran kills visitors
- ✅ Arsonist douse/ignite
- ✅ Werewolf full moon
- ✅ Juggernaut escalation
- ✅ Amnesiac remember
- ✅ Retributionist revive
- ✅ State management (night/day)

---

## 🎯 RECOMMENDED PRIORITY

**Must-Have (32 hours):**
1. Ability use limits (HIGHEST PRIORITY - Veteran, Jailor can spam)
2. Executioner target tracking
3. Jester haunt
4. Transport swap

**Should-Have (36 hours):**
5. Cooldown system
6. Bodyguard counterattack
7. Godfather/Mafioso coordination
8. Vigilante guilt
9. Witch control
10. Cleaned bodies display

**Nice-to-Have (20 hours):**
11. Forger/Disguiser/Hypnotist full implementation
12. UI polish and displays

**Current Status:** Game is 95% feature-complete for abilities, but needs 32 hours of critical mechanics to reach 100% parity with Town of Salem.
