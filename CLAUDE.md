# CLAUDE.md

Behavioral guidelines and project conventions. These guidelines bias toward caution over speed — for trivial tasks, use judgment.

---

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

---

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

---

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that **your** changes made unused.
- Don't remove pre-existing dead code unless asked.

Every changed line should trace directly to the user's request.

---

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

---

## 5. Code Style

### Docstrings — Google style

All public functions and classes must have Google-style docstrings.

```python
def fetch_price(ticker: str, date: str) -> float:
    """Fetch the closing price of a stock on the given date.

    Args:
        ticker: Stock ticker symbol (e.g., '005930' for 삼성전자).
        date: Date string in YYYYMMDD format.

    Returns:
        Closing price as a float.
    """
```

### Comments — English only

All comments must be in English. Proper nouns that have no natural English equivalent (e.g., Korean stock names like 삼성전자, 카카오) may be left in their original script.

```python
# Fetch deviation signals for 삼성전자 from LS증권 Open API
```

---

## 6. Testing

**New feature = new tests. No exceptions.**

### Where tests live

| Scope | Location |
|-------|----------|
| Backend `app` service | `backend/tests/app/` |
| Backend `bot` service | `backend/tests/bot/` |
| Backend `monitor` service | `backend/tests/monitor/` |
| `lsapi` package | `lsapi/tests/` |
| Root-level integration | `tests/` |

Test files follow `test_<module>.py` naming. Test functions follow `test_<what_it_tests>`.

### Running tests

```bash
# All tests
uv run pytest

# Specific service
uv run pytest backend/tests/monitor/

# Skip slow tests
uv run pytest -m "not slow"
```

Tests run automatically on `git push` via pre-commit. Ruff lint/format runs on every commit.

---

## 7. Decisions Log

If a decision was driven by business context — not derivable from the code itself — record it in `docs/decisions.md`.

Examples of what belongs there:
- Why monitor thresholds are set to specific values
- Why a particular API endpoint was chosen over another
- Why a service was designed to run as a sidecar vs. standalone
- Why a column type was chosen for domain-specific reasons

Format:

```markdown
## YYYY-MM-DD: <Title>

**Context:** What situation required a decision.

**Decision:** What was decided.

**Reason:** Why — especially the business or domain logic behind it.
```

---

## 8. Testing — Path Setup

`conftest.py` is for fixtures only. Never use it to manipulate `sys.path`.

To make internal packages (e.g. `monitor`, `shared`) importable in tests, add `pythonpath` to `[tool.pytest.ini_options]` in the root `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["backend"]
```

---

## 9. Project Structure

```
bicquant/                           # uv workspace root
├── backend/                        # bicquant-backend package
│   ├── app/                        # FastAPI REST API
│   │   ├── main.py
│   │   ├── routers/
│   │   └── services/
│   ├── bot/                        # Telegram bot (long-running)
│   │   └── main.py
│   ├── monitor/                    # Deviation monitor (long-running)
│   │   ├── main.py
│   │   ├── deviation.py
│   │   ├── notifier.py
│   │   └── sidecar.py
│   ├── shared/                     # Shared DB models, queries, config
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── models/
│   │   └── queries/
│   ├── config/                     # Hydra config files per service/env
│   │   ├── app/{default,dev,prod}.yaml
│   │   ├── bot/{default,dev,prod}.yaml
│   │   └── monitor/{default,dev,prod}.yaml
│   ├── alembic/                    # DB migrations
│   └── tests/
│       ├── app/
│       ├── bot/
│       └── monitor/
├── lsapi/                          # LS Securities OpenAPI Python client
│   ├── src/lsapi/
│   │   ├── client.py
│   │   ├── ws_client.py
│   │   ├── auth.py
│   │   ├── catalog.py
│   │   └── specs/                  # Built API specs (JSON)
│   ├── scripts/                    # crawl_docs.py, build_specs.py
│   └── tests/
├── frontend/                       # React + Vite
├── docs/
│   ├── architecture.md
│   ├── development.md
│   ├── setup.md
│   └── decisions.md                # Business context decisions
├── tests/                          # Root-level integration tests
├── docker-compose.yml
└── pyproject.toml                  # Workspace root: ruff + pytest config
```

---

## 10. Key Commands

### Development

```bash
# Start all services
docker compose up -d
```

### Database Migrations (Alembic)

```bash
cd backend

# Create a new migration
uv run alembic revision --autogenerate -m "<description>"

# Apply migrations
uv run alembic upgrade head

# Downgrade one step
uv run alembic downgrade -1
```

### Lint & Format

```bash
# Check
uv run ruff check .

# Fix + format
uv run ruff check --fix . && uv run ruff format .
```

---

## 11. Environment

Secrets and environment variables live in `.env` (gitignored). See `.env.example` for the required keys.

Services consume config via **Hydra** (`backend/config/`). The active environment is controlled by the `ENV` variable (`dev` / `prod`).

---

**These guidelines are working if:** diffs stay focused, rewrites from overcomplication are rare, and clarifying questions come before implementation rather than after mistakes.
