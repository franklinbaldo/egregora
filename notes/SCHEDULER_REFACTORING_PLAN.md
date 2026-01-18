# Jules Scheduler Refactoring Plan

## Current Issues

### 1. Code Complexity
- **841 lines** in a single file
- `run_cycle_step()`: 140 lines with 5 levels of nesting
- `run_scheduler()`: Duplicate logic for persona loading
- Mixed abstraction levels (git commands + business logic)

### 2. Poor Separation of Concerns
```
scheduler.py currently contains:
├── Sprint management
├── Configuration loading
├── Persona loading & parsing
├── Git branch operations
├── GitHub PR operations
├── Jules API interactions
├── Cycle state management
└── Schedule checking
```

### 3. Hard to Test
- Functions are tightly coupled
- No clear interfaces
- Side effects everywhere (print statements, git commands)
- Hard to mock dependencies

### 4. Unclear Flow
- Cycle vs Scheduled mode logic is intertwined
- Hard to follow what happens in each scenario
- State transitions are implicit

---

## Refactoring Goals

1. **Readability**: Clear, self-documenting code
2. **Testability**: Easy to unit test each component
3. **Maintainability**: Easy to modify one part without breaking others
4. **Understandability**: Flow should be obvious

---

## New Architecture

### Domain Models (dataclasses)

```python
@dataclass
class PersonaConfig:
    """Immutable persona configuration."""
    id: str
    emoji: str
    description: str
    prompt_body: str
    journal_entries: str

@dataclass
class CycleState:
    """Current state of the cycle."""
    last_session_id: str | None
    last_persona_id: str | None
    next_persona_id: str
    should_increment_sprint: bool

@dataclass
class SessionRequest:
    """Parameters for creating a Jules session."""
    persona_id: str
    title: str
    prompt: str
    branch: str
    owner: str
    repo: str
    automation_mode: str = "AUTO_CREATE_PR"
    require_plan_approval: bool = False
```

### Separated Classes

#### 1. PersonaLoader
```python
class PersonaLoader:
    """Loads and parses persona configurations."""

    def load_personas(self, cycle_list: list[str]) -> list[PersonaConfig]
    def load_persona(self, path: Path, context: dict) -> PersonaConfig
    def collect_journals(self, persona_dir: Path) -> str
```

#### 2. CycleStateManager
```python
class CycleStateManager:
    """Manages cycle state and progression."""

    def find_last_cycle_session(self, ...) -> CycleState
    def advance_cycle(self, current_persona: str, cycle: list[str]) -> tuple[str, bool]
    def should_increment_sprint(self, next_idx: int) -> bool
```

#### 3. BranchManager
```python
class BranchManager:
    """Handles all git branch operations."""

    def ensure_jules_branch_exists(self) -> None
    def create_session_branch(self, base: str, persona: str, ...) -> str
    def is_drifted(self) -> bool
    def rotate_drifted_branch(self) -> None
    def update_from_main(self) -> bool
```

#### 4. PRManager
```python
class PRManager:
    """Handles PR operations."""

    def is_green(self, pr_details: dict) -> bool
    def merge_into_jules(self, pr_number: int) -> None
    def find_by_session_id(self, session_id: str, prs: list) -> dict | None
```

#### 5. SessionOrchestrator
```python
class SessionOrchestrator:
    """Coordinates session creation."""

    def create_cycle_session(self, persona: PersonaConfig, branch: str) -> str
    def create_scheduled_session(self, persona: PersonaConfig) -> str
    def handle_stuck_session(self, session_id: str, state: str) -> None
```

### New Flow

#### Cycle Mode
```python
def execute_cycle_tick(dry_run: bool) -> None:
    """Execute one cycle tick (clear, linear flow)."""

    # 1. SETUP
    personas = persona_loader.load_personas(cycle_list)
    branch_manager.ensure_jules_branch_exists()

    # 2. FIND LAST SESSION
    state = cycle_manager.find_last_cycle_session(client, personas, open_prs)

    # 3. HANDLE LAST SESSION (if exists)
    if state.last_session_id:
        pr = pr_manager.find_by_session_id(state.last_session_id, open_prs)

        if pr and pr_manager.is_green(pr):
            pr_manager.merge_into_jules(pr["number"])
            next_persona, should_increment = cycle_manager.advance_cycle(
                state.last_persona_id, [p.id for p in personas]
            )
            if should_increment:
                sprint_manager.increment_sprint()
        elif pr and not pr_manager.is_green(pr):
            return  # Wait for PR to pass
        else:
            orchestrator.handle_stuck_session(state.last_session_id)
            return

    # 4. START NEXT SESSION
    next_persona = personas[get_next_index(...)]
    branch = branch_manager.create_session_branch(...)
    session_id = orchestrator.create_cycle_session(next_persona, branch)
    print(f"✓ Started {next_persona.emoji} {next_persona.id}: {session_id}")
```

#### Scheduled Mode
```python
def execute_scheduled_tick(run_all: bool, prompt_id: str | None) -> None:
    """Execute scheduled personas (clear, linear flow)."""

    # 1. SETUP
    personas = persona_loader.load_personas([])
    schedules = load_schedule_registry()

    # 2. FILTER PERSONAS
    for persona in personas:
        if should_run(persona, schedules, run_all, prompt_id):
            session_id = orchestrator.create_scheduled_session(persona)
            print(f"✓ Started {persona.emoji} {persona.id}: {session_id}")
```

---

## Implementation Steps

### Phase 1: Extract Models
- [ ] Create domain models (PersonaConfig, CycleState, SessionRequest)
- [ ] Create new file: `.team/repo/scheduler_models.py`

### Phase 2: Extract Loader
- [ ] Create PersonaLoader class
- [ ] Move prompt parsing logic
- [ ] Move journal collection
- [ ] Create new file: `.team/repo/scheduler_loader.py`

### Phase 3: Extract Managers
- [ ] Create BranchManager class
- [ ] Create PRManager class
- [ ] Create CycleStateManager class
- [ ] Create SessionOrchestrator class
- [ ] Create new file: `.team/repo/scheduler_managers.py`

### Phase 4: Refactor Main Functions
- [ ] Rewrite `run_cycle_step` as `execute_cycle_tick`
- [ ] Rewrite scheduled mode as `execute_scheduled_tick`
- [ ] Simplify `run_scheduler` as orchestrator

### Phase 5: Testing & Cleanup
- [ ] Update unit tests
- [ ] Test cycle mode manually
- [ ] Test scheduled mode manually
- [ ] Remove old code
- [ ] Update documentation

---

## Benefits

### Before (Current)
```python
# 140-line function with 5 levels of nesting
def run_cycle_step(...):
    # Setup
    cycle_ids = [...]
    ensure_jules_branch_exists()
    last_session_id, last_pid = get_last_cycle_session(...)

    # Handle last session (80 lines of nested if/elif/else)
    if last_session_id and last_pid:
        pr = get_pr_by_session_id(...)
        if pr:
            if not is_pr_green(...):
                return
            merge_pr_into_jules(...)
            if last_pid in cycle_ids:
                idx = cycle_ids.index(...)
                # ...more nesting...
        else:
            merged_pr = get_pr_by_session_id_any_state(...)
            if merged_pr and merged_pr.get("mergedAt"):
                # ...more logic...
            elif merged_pr and ...:
                # ...more logic...
            else:
                try:
                    # ...more logic...

    # Start next session (40 lines)
    # ...
```

### After (Refactored)
```python
# ~40 lines, clear linear flow, easy to read
def execute_cycle_tick(dry_run: bool) -> None:
    """Execute one cycle tick."""

    personas = persona_loader.load_personas(cycle_list)
    branch_manager.ensure_jules_branch_exists()

    state = cycle_manager.find_last_cycle_session(client, personas, open_prs)

    if state.last_session_id:
        handle_previous_session(state, dry_run)
        if state.needs_wait:
            return

    next_persona = get_next_persona(state, personas)
    start_cycle_session(next_persona, state, dry_run)
```

---

## Risk Mitigation

1. **Keep old code temporarily**: Rename to `scheduler_old.py`
2. **Add integration tests**: Test full flow before removing old code
3. **Incremental rollout**: Can switch back if issues arise
4. **Preserve behavior**: All existing functionality must work identically
