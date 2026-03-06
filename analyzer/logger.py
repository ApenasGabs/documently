"""
Documently — Logger
Funções de log com timestamp e contexto de projeto/arquivo.
"""

import json
import os
from datetime import datetime
from pathlib import Path


TELEMETRY_ENABLED = os.getenv("TELEMETRY_ENABLED", "1").lower() not in {"0", "false", "no"}
TELEMETRY_LOG_DIR = Path(os.getenv("TELEMETRY_LOG_DIR", "/output/logs"))
TELEMETRY_LOG_FILE = os.getenv("TELEMETRY_LOG_FILE", "ollama_telemetry.jsonl")
_TELEMETRY_PATH_CACHE: Path | None = None
_TELEMETRY_FALLBACK_WARNED = False


def _safe_json(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)


def _resolve_telemetry_path() -> Path:
    global _TELEMETRY_PATH_CACHE, _TELEMETRY_FALLBACK_WARNED
    if _TELEMETRY_PATH_CACHE is not None:
        return _TELEMETRY_PATH_CACHE

    candidates = [
        TELEMETRY_LOG_DIR,
        Path("/tmp/documently-logs"),
        Path("./logs"),
    ]

    for index, directory in enumerate(candidates):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            out = directory / TELEMETRY_LOG_FILE
            with out.open("a", encoding="utf-8"):
                pass
            _TELEMETRY_PATH_CACHE = out
            if index > 0 and not _TELEMETRY_FALLBACK_WARNED:
                print(
                    f"[logger] fallback de telemetria ativo em {directory} "
                    f"(sem permissão em {TELEMETRY_LOG_DIR})",
                    flush=True,
                )
                _TELEMETRY_FALLBACK_WARNED = True
            return out
        except Exception:
            continue

    raise PermissionError("Nenhum diretório gravável para telemetria")


def log_telemetry(event: str, payload: dict):
    if not TELEMETRY_ENABLED:
        return
    try:
        record = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "event": event,
            **payload,
        }
        out = _resolve_telemetry_path()
        with out.open("a", encoding="utf-8") as fp:
            fp.write(_safe_json(record) + "\n")
    except Exception:
        # Telemetria nunca deve derrubar a análise principal
        pass


def log(level: str, msg: str, project: str = "", file: str = ""):
    ts = datetime.now().strftime("%H:%M:%S")
    parts = [f"[{ts}]", f"{level:<5}"]
    if project:
        parts.append(f"[{project}]")
    if file:
        parts.append(f"[{file}]")
    parts.append(msg)
    print(" | ".join(parts), flush=True)

def log_info(msg, project="", file=""):  log("INFO ", msg, project, file)
def log_ok(msg, project="", file=""):    log("OK   ", msg, project, file)
def log_warn(msg, project="", file=""):  log("WARN ", msg, project, file)
def log_err(msg, project="", file=""):   log("ERROR", msg, project, file)
def log_skip(msg, project="", file=""):  log("SKIP ", msg, project, file)