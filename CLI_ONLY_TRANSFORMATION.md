# Hermes Agent — Minimal CLI Software-Dev Agent

Stripped-down agent for **`hermes chat`** only: software-development skills, terminal/file/browser tools, and simple file-backed session memory.

---

## What you use

```bash
hermes chat          # interactive CLI (classic prompt_toolkit REPL)
```

Removed surfaces: web dashboard, TUI (`--tui`), Electron GUI, cron, ACP editor bridge, messaging gateway, external memory plugins.

---

## Top-level layout (after trim)

| Path | Purpose |
|------|---------|
| `cli.py` | Classic CLI REPL |
| `run_agent.py` | Agent conversation loop |
| `model_tools.py` / `toolsets.py` | Tool registry |
| `hermes_state.py` | SQLite session DB (resume, history) |
| `agent/` | Agent core (init, transports, compression) |
| `tools/` | Tool implementations |
| `hermes_cli/` | CLI commands, config, auth, setup |
| `providers/` | Model provider profile registry |
| `plugins/` | Browser + web search + model-provider plugins only |
| `gateway/` | Minimal stubs (`session_context`, `status`) |
| `skills/software-development/` | Bundled dev skills |
| `locales/` | i18n for approval prompts |

---

## Deleted directories

| Removed | Reason |
|---------|--------|
| `acp_registry/`, `acp_adapter/` | Editor ACP integration |
| `apps/` | Electron desktop GUI |
| `assets/`, `infographic/` | Marketing / static assets |
| `cron/` | Scheduled jobs |
| `datagen-config-examples/` | Batch/datagen examples |
| `optional-mcps/`, `optional-skills/` | Optional catalogs |
| `scripts/`, `tests/` | Dev scripts and test suite |
| `web/`, `ui-tui/` | Dashboard and Ink TUI |
| `plugins/memory/*/` | Honcho, Mem0, Hindsight, etc. |
| `plugins/context_engine`, `observability`, `security-guidance`, `disk-cleanup`, `dashboard_auth` | Optional runtime plugins |
| All `plugins/model-providers/*` except **anthropic**, **gemini**, **openrouter** | Extra inference providers |

---

## Model providers (kept)

| Provider | How |
|----------|-----|
| **OpenAI** | `openai-api` via `OPENAI_API_KEY` in `hermes_cli/auth.py` |
| **Anthropic** | `plugins/model-providers/anthropic/` |
| **Google (Gemini)** | `plugins/model-providers/gemini/` + `gemini` in auth |
| **OpenRouter** | `plugins/model-providers/openrouter/` |

---

## Memory (single system)

| Component | Role |
|-----------|------|
| `tools/memory_tool.py` | `MEMORY.md` + `USER.md` file-backed notes |
| `hermes_state.py` | Session DB for chat continuation / search |
| `memory` tool in toolsets | Agent reads/writes built-in memory files |

**Removed:** all `plugins/memory/*` backends (Honcho, Mem0, OpenViking, etc.). Set `memory.provider` in config has no effect — no plugins to load.

---

## Skills (kept)

**Bundled:** `skills/software-development/` — plan, TDD, debugging, patch, spike, debuggers, skill-authoring.

---

## Plugins (kept)

- `plugins/browser/` — browser automation backends
- `plugins/web/` — web search/extract backends
- `plugins/model-providers/{anthropic,gemini,openrouter}/`
- `plugins/memory/__init__.py` — empty scanner (no provider subdirs)

---

## CLI commands stubbed / removed

| Command | Status |
|---------|--------|
| `hermes chat` | **Active** |
| `hermes gateway` / `whatsapp` / `send` / `slack` | Stub (messaging removed earlier) |
| `hermes cron` | Stub — cron backend deleted |
| `hermes dashboard` | Stub — `web_server.py` deleted |
| `hermes gui` | Stub — `apps/` deleted |
| `hermes acp` | Stub — `acp_adapter/` deleted |
| `--tui` / `HERMES_TUI` | Stub — `ui-tui/` deleted |
| `/cron` in chat | Disabled message |

---

## Tools removed from agent

- `cronjob` tool + `tools/cronjob_tools.py`
- `hermes-cron`, `hermes-acp` toolsets
- Messaging tools (earlier pass)

---

## Dependencies trimmed (`pyproject.toml`)

- Removed from core: `croniter`, `fastapi`, `uvicorn` (no cron / no embedded dashboard server)

---

## Optional follow-ups

- Trim `hermes_cli/auth.py` `PROVIDER_REGISTRY` to four providers only (plugin dirs already pruned).
- Remove `batch_runner.py`, `mcp_serve.py`, `mini_swe_runner.py` if batch/MCP-serve modes are unused.
- Remove `mcp` CLI if you do not need MCP tool servers.
- Simplify `hermes_cli/memory_setup.py` to built-in-only flows.

---

*Last updated: minimal agent trim pass.*
