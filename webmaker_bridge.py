#!/usr/bin/env python3
"""Headless Hermes bridge for Webmaker.

Reads one JSON request from stdin and writes Webmaker-compatible NDJSON events
to stdout. This module intentionally keeps host state isolated through
HERMES_HOME and validates the requested workspace root before running tools.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List

from run_agent import AIAgent


WEBMAKER_SYSTEM_PROMPT = """You are Hermes running inside Webmaker.

Build and edit complete frontend websites and apps inside the session workspace
under .webmaker/workspaces/. Stay frontend-only: do not add backend services,
auth systems, databases, or secrets. Never write to the Webmaker host app
(webmaker/app/, webmaker/components/, etc.) — only the session workspace root.

On greenfield workspaces, follow the preloaded create-new-project skill to
scaffold the project. The workspace root is the project directory.

Before completion, inspect your changes and run an appropriate verification
command when the project supports it.
"""


def register_repo_skills_dir() -> None:
    """Expose bundled repo skills (e.g. create-new-project) to skill_view."""
    repo_skills = Path(__file__).resolve().parent / "skills"
    if not repo_skills.is_dir():
        return

    import agent.skill_utils as skill_utils

    original = skill_utils.get_external_skills_dirs

    def patched() -> list[Path]:
        dirs = original()
        resolved = repo_skills.resolve()
        if resolved not in {d.resolve() for d in dirs}:
            return [repo_skills, *dirs]
        return dirs

    skill_utils.get_external_skills_dirs = patched  # type: ignore[assignment]


def _workspace_has_package_json(request: Dict[str, Any]) -> bool:
    workspace_raw = request.get("workspaceRoot")
    if isinstance(workspace_raw, str) and workspace_raw.strip():
        if (Path(workspace_raw) / "package.json").is_file():
            return True

    current = request.get("currentProject")
    if isinstance(current, dict):
        files = current.get("files")
        if isinstance(files, dict):
            pkg = files.get("/package.json")
            if isinstance(pkg, dict):
                code = pkg.get("code")
                if isinstance(code, str) and code.strip():
                    return True

    return False


def is_greenfield_workspace(request: Dict[str, Any]) -> bool:
    if request.get("greenfield") is True:
        return True
    return not _workspace_has_package_json(request)


def build_webmaker_system_prompt(request: Dict[str, Any]) -> str:
    parts = [WEBMAKER_SYSTEM_PROMPT]

    if not is_greenfield_workspace(request):
        return parts[0]

    register_repo_skills_dir()
    try:
        from agent.skill_commands import build_preloaded_skills_prompt

        skill_prompt, loaded, _missing = build_preloaded_skills_prompt(["create-new-project"])
        if skill_prompt:
            parts.append(skill_prompt)
        if loaded:
            parts.append(
                "[MANDATORY FIRST STEP — greenfield workspace (no package.json yet): "
                "run a terminal command to scaffold IN PLACE before reading or editing files: "
                "npx create-next-app@latest . --yes. "
                "Do not manually write package.json, copy template files, or create a nested subfolder. "
                "After scaffold succeeds, continue feature work in the workspace root.]"
            )
        else:
            parts.append(
                "[Greenfield Webmaker workspace: run skill_view('create-new-project'), then "
                "scaffold in the workspace root before building features.]"
            )
    except Exception:
        parts.append(
            "[Greenfield Webmaker workspace: scaffold in the workspace root using "
            "create-new-project before building features.]"
        )

    return "\n\n".join(parts)


def emit(event: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(event, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def read_hermes_runtime_info() -> Dict[str, Any]:
    model = os.environ.get("WEBMAKER_HERMES_MODEL") or os.environ.get("HERMES_MODEL") or ""
    provider = os.environ.get("WEBMAKER_HERMES_PROVIDER") or os.environ.get("HERMES_PROVIDER") or ""

    if not model or not provider:
        try:
            from hermes_constants import get_hermes_home
            from hermes_cli.profiles import _read_config_model

            config_model, config_provider = _read_config_model(Path(get_hermes_home()))
            if not model and config_model:
                model = str(config_model)
            if not provider and config_provider:
                provider = str(config_provider)
        except Exception:
            pass

    hermes_home = os.environ.get("HERMES_HOME", "")
    if not hermes_home:
        try:
            from hermes_constants import get_hermes_home
            hermes_home = str(get_hermes_home())
        except Exception:
            hermes_home = ""

    return {
        "type": "runtime_info",
        "model": model or "Hermes configured default",
        "provider": provider or "Hermes configured default",
        "hermesHome": hermes_home,
    }


def read_request() -> Dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        raise ValueError("No Webmaker request was provided.")

    first_line = raw.splitlines()[0]
    parsed = json.loads(first_line)
    if not isinstance(parsed, dict):
        raise ValueError("Webmaker request must be a JSON object.")
    return parsed


def safe_workspace_root(value: Any) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("workspaceRoot must be a non-empty string.")

    workspace = Path(value).resolve()
    allowed_raw = os.environ.get("WEBMAKER_WORKSPACE_ROOT")
    if allowed_raw:
        allowed = Path(allowed_raw).resolve()
        try:
            workspace.relative_to(allowed)
        except ValueError as exc:
            raise ValueError(f"workspaceRoot must be inside {allowed}") from exc

    workspace.mkdir(parents=True, exist_ok=True)
    return workspace


def latest_user_message(messages: Iterable[Dict[str, Any]]) -> str:
    for message in reversed(list(messages)):
        if message.get("role") == "user" and isinstance(message.get("content"), str):
            return message["content"]
    return "Continue improving the current Webmaker project."


def conversation_history(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    history: List[Dict[str, str]] = []
    for message in messages[:-1]:
        role = message.get("role")
        content = message.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            history.append({"role": role, "content": content})
    return history


def compact_text(value: Any, limit: int = 1200) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}..."


def event_kind_for_tool(tool_name: str) -> str:
    lowered = tool_name.lower()
    if "write" in lowered:
        return "edit"
    if "patch" in lowered:
        return "patch"
    if "read" in lowered:
        return "read"
    if "search" in lowered or "web" in lowered:
        return "search"
    if "terminal" in lowered or "process" in lowered or "execute" in lowered:
        return "verify"
    if "skill" in lowered:
        return "inspect"
    return "runtime"


def collect_targets(tool_name: str, args: Any) -> List[str]:
    if not isinstance(args, dict):
        return []

    targets: List[str] = []
    for key in ("path", "file_path", "filepath", "target", "cwd"):
        value = args.get(key)
        if isinstance(value, str) and value.strip():
            targets.append(value.strip())

    for key in ("paths", "file_paths", "files"):
        value = args.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item.strip():
                    targets.append(item.strip())
                elif isinstance(item, dict):
                    path_value = item.get("path") or item.get("file_path")
                    if isinstance(path_value, str) and path_value.strip():
                        targets.append(path_value.strip())

    if tool_name == "patch":
        patch_body = args.get("patch")
        if isinstance(patch_body, str):
            for line in patch_body.splitlines():
                for prefix in ("*** Update File: ", "*** Add File: ", "*** Delete File: "):
                    if line.startswith(prefix):
                        targets.append(line[len(prefix):].strip())

    command = args.get("cmd") or args.get("command")
    if isinstance(command, str) and command.strip():
        targets.append(command.strip())

    query = args.get("query") or args.get("pattern")
    if isinstance(query, str) and query.strip() and not targets:
        targets.append(query.strip())

    deduped: List[str] = []
    for target in targets:
        if target not in deduped:
            deduped.append(target)
    return deduped[:8]


def result_summary(result: Any) -> str:
    if result is None:
        return ""

    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except Exception:
            return compact_text(result)
    else:
        parsed = result

    if isinstance(parsed, dict):
        parts: List[str] = []
        for key in ("error", "message", "output", "stdout", "stderr", "result"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(f"{key}: {value.strip()}")
        if parts:
            return compact_text("\n".join(parts))
        return compact_text(json.dumps(parsed, ensure_ascii=False))

    return compact_text(parsed)


def activity(
    tool_call_id: str | None,
    tool_name: str,
    status: str,
    detail: str,
    args: Any = None,
    result: Any = None,
) -> Dict[str, Any]:
    targets = collect_targets(tool_name, args)
    summary = result_summary(result) if status == "completed" else ""
    if summary:
        detail = f"{detail}\n\n{summary}"
    payload = {
        "id": tool_call_id or f"hermes-{uuid.uuid4().hex[:10]}",
        "kind": event_kind_for_tool(tool_name),
        "status": status,
        "title": tool_name.replace("_", " ").title(),
        "detail": compact_text(detail, 1800),
        "tool": tool_name,
    }
    if targets:
        payload["targets"] = targets
    return {
        "type": "activity",
        "activity": payload,
    }


class ReasoningEmitter:
    def __init__(self) -> None:
        self.parts: list[str] = []
        self.last_emitted_len = 0

    def append(self, text: Any) -> None:
        chunk = str(text)
        if not chunk:
            return
        self.parts.append(chunk)
        current = self.text()
        if len(current) - self.last_emitted_len >= 600:
            self.emit("active")

    def text(self) -> str:
        return "".join(self.parts).strip()

    def emit(self, status: str = "active") -> None:
        text = self.text()
        if not text:
            return
        self.last_emitted_len = len(text)
        detail = "Reasoned." if status == "completed" else compact_text(text[-800:], 800)
        emit(
            {
                "type": "activity",
                "activity": {
                    "id": "hermes-reasoning",
                    "kind": "plan",
                    "status": status,
                    "title": "Reasoning",
                    "detail": detail,
                    "tool": "hermes.reasoning",
                },
            }
        )


def configured_model(request: Dict[str, Any]) -> tuple[str, str]:
    env_model = os.environ.get("WEBMAKER_HERMES_MODEL") or os.environ.get("HERMES_MODEL")
    if env_model:
        return env_model, "environment"

    request_model = request.get("model")
    if isinstance(request_model, str) and request_model.strip():
        return request_model.strip(), "request"

    return "", "Hermes default"


def configured_provider(request: Dict[str, Any]) -> tuple[str, str]:
    env_provider = os.environ.get("WEBMAKER_HERMES_PROVIDER") or os.environ.get("HERMES_PROVIDER")
    if env_provider:
        return env_provider, "environment"

    request_provider = request.get("provider")
    if isinstance(request_provider, str) and request_provider.strip():
        return request_provider.strip(), "request"

    try:
        info = read_hermes_runtime_info()
        provider = info.get("provider")
        if isinstance(provider, str) and provider and provider != "Hermes configured default":
            return provider, "Hermes config"
    except Exception:
        pass

    return "", "Hermes default"


def main() -> int:
    try:
        if "--runtime-info" in sys.argv:
            emit(read_hermes_runtime_info())
            return 0

        request = read_request()
        workspace = safe_workspace_root(request.get("workspaceRoot"))
        os.chdir(workspace)
        os.environ["WEBMAKER_HERMES_TERMINAL_POLICY"] = "1"
        os.environ["WEBMAKER_HERMES_FILE_POLICY"] = "1"

        messages = request.get("messages")
        if not isinstance(messages, list):
            raise ValueError("messages must be an array.")

        model, model_source = configured_model(request)
        provider, provider_source = configured_provider(request)
        system_prompt = build_webmaker_system_prompt(request)
        emit(
            {
                "type": "activity",
                "activity": {
                    "id": "hermes-runtime",
                    "kind": "runtime",
                    "status": "completed",
                    "title": "Hermes runtime",
                    "detail": (
                        f"Model: {model or 'Hermes configured default'}"
                        f" ({model_source}); provider: {provider or 'Hermes configured default'}"
                        f" ({provider_source})."
                    ),
                    "tool": "hermes.runtime",
                },
            }
        )

        toolsets = ["webmaker"]
        reasoning = ReasoningEmitter()
        agent = AIAgent(
            model=model,
            provider=provider or None,
            session_id=str(request.get("sessionId") or uuid.uuid4()),
            enabled_toolsets=toolsets,
            quiet_mode=True,
            platform="webmaker",
            ephemeral_system_prompt=system_prompt,
            tool_start_callback=lambda call_id, name, args: emit(
                activity(call_id, name, "active", "Hermes started a workspace tool.", args=args)
            ),
            tool_complete_callback=lambda call_id, name, args, result: (
                emit(
                    activity(
                        call_id,
                        name,
                        "completed",
                        "Hermes completed a workspace tool.",
                        args=args,
                        result=result,
                    )
                ),
                emit({"type": "project"}),
            ),
            stream_delta_callback=lambda delta: (
                emit({"type": "delta", "tail": str(delta), "tokenCount": max(1, len(str(delta)) // 4)})
                if delta is not None and str(delta) != "None"
                else None
            ),
            reasoning_callback=reasoning.append,
            status_callback=lambda status: emit(
                {
                    "type": "activity",
                    "activity": {
                        "id": f"status-{uuid.uuid4().hex[:10]}",
                        "kind": "runtime",
                        "status": "completed",
                        "title": "Hermes status",
                        "detail": str(status)[:500],
                        "tool": "hermes.status",
                    },
                }
            ),
        )
        agent.session_cwd = str(workspace)

        result = agent.run_conversation(
            latest_user_message(messages),
            system_message=system_prompt,
            conversation_history=conversation_history(messages),
            task_id=str(request.get("sessionId") or uuid.uuid4()),
        )
        reasoning.emit("completed")
        summary = result.get("final_response") if isinstance(result, dict) else str(result)
        emit({"type": "complete", "summary": summary or "Hermes generation finished.", "tokenCount": 0})
        return 0
    except KeyboardInterrupt:
        emit({"type": "aborted", "summary": "Hermes generation was aborted.", "tokenCount": 0})
        return 0
    except Exception as exc:
        emit({"type": "error", "message": str(exc)})
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
