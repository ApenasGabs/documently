"""
Documently — Loop principal
Varre /projects/*, detecta o tipo de projeto automaticamente e grava:
  /output/docs/<projeto>.md
  /output/status/<projeto>.json
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime

from profiles import PROFILES, detect_profile

# ── Configuração via env ──────────────────────────────────────────────
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL        = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS_PER_CHUNK", 3000))
PROJECTS_DIR = Path("/projects")
DOCS_DIR     = Path("/output/docs")
STATUS_DIR   = Path("/output/status")

DOCS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)


# ── Logger simples ────────────────────────────────────────────────────

def log(level: str, msg: str, project: str = "", file: str = ""):
    """Loga no formato: [HH:MM:SS] LEVEL | projeto | arquivo | msg"""
    ts = datetime.now().strftime("%H:%M:%S")
    parts = [f"[{ts}]", f"{level:<5}"]
    if project:
        parts.append(f"[{project}]")
    if file:
        parts.append(f"[{file}]")
    parts.append(msg)
    print(" | ".join(parts), flush=True)

def log_info(msg, project="", file=""):  log("INFO", msg, project, file)
def log_ok(msg, project="", file=""):    log("OK   ", msg, project, file)
def log_warn(msg, project="", file=""):  log("WARN", msg, project, file)
def log_err(msg, project="", file=""):   log("ERROR", msg, project, file)
def log_skip(msg, project="", file=""):  log("SKIP", msg, project, file)


# ── Helpers ───────────────────────────────────────────────────────────

def wait_for_ollama(retries=20, delay=3):
    log_info("aguardando Ollama ficar pronto...")
    for i in range(retries):
        try:
            r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if r.status_code == 200:
                log_ok(f"Ollama pronto em {OLLAMA_HOST}")
                return
        except Exception as e:
            log_warn(f"tentativa {i+1}/{retries} falhou: {e}")
        time.sleep(delay)
    raise RuntimeError("Ollama não respondeu a tempo.")


def load_status(project_name: str) -> dict:
    path = STATUS_DIR / f"{project_name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {
        "project": project_name,
        "profile": None,
        "files": {},
        "started_at": None,
        "finished_at": None,
    }


def save_status(project_name: str, status: dict):
    path = STATUS_DIR / f"{project_name}.json"
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False))


def chunk_text(content: str, max_tokens: int = MAX_TOKENS) -> list[str]:
    lines = content.splitlines(keepends=True)
    chunks, current, count = [], [], 0
    for line in lines:
        t = len(line) // 4
        if count + t > max_tokens and current:
            chunks.append("".join(current))
            current, count = [line], t
        else:
            current.append(line)
            count += t
    if current:
        chunks.append("".join(current))
    return chunks or [""]


def analyze_chunk(chunk: str, context_summary: str, filename: str,
                  chunk_idx: int, total: int, profile: dict) -> str:
    ext = Path(filename).suffix
    prompt = f"""Você é um analisador de código especialista em {profile['lang_label']}.

Contexto já analisado (resumo): {context_summary[-600:] if context_summary else "Nenhum — este é o início do arquivo."}

Arquivo: {filename}  (chunk {chunk_idx + 1} de {total})

```{ext.lstrip('.')}
{chunk}
```

{profile['prompt_focus']}

Responda em português, de forma concisa (máx 300 palavras)."""

    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "temperature": 0.1,
                "num_predict": 512,
            },
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"].strip()


# ── Processamento ─────────────────────────────────────────────────────

def process_file(filepath: Path, context_window: list,
                 status_files: dict, profile: dict, project: str) -> str:
    rel = str(filepath)
    fname = filepath.name
    file_status = status_files.get(rel, {"chunks_done": 0, "total_chunks": 0, "done": False})

    try:
        content = filepath.read_text(errors="replace")
    except Exception as e:
        log_err(f"não foi possível ler: {e}", project, fname)
        return f"> ⚠️ Não foi possível ler `{fname}`: {e}\n"

    chunks = chunk_text(content)
    total  = len(chunks)
    file_status["total_chunks"] = total
    status_files[rel] = file_status

    if file_status.get("done"):
        log_skip("já analisado anteriormente", project, fname)
        return ""

    log_info(f"iniciando — {total} chunk(s)", project, fname)
    doc_parts = [f"\n---\n## 📄 `{fname}`\n"]
    context_summary = "\n".join(context_window[-5:])

    for i, chunk in enumerate(chunks):
        if i < file_status["chunks_done"]:
            log_skip(f"chunk {i+1}/{total} já processado", project, fname)
            continue

        log_info(f"chunk {i+1}/{total} → enviando para Ollama...", project, fname)
        start = time.time()
        analysis = analyze_chunk(chunk, context_summary, fname, i, total, profile)
        elapsed = round(time.time() - start, 1)
        log_ok(f"chunk {i+1}/{total} concluído em {elapsed}s", project, fname)

        doc_parts.append(f"### Chunk {i+1}/{total}\n\n{analysis}\n")

        context_window.append(f"[{fname} c{i+1}]: {analysis[:200]}")
        if len(context_window) > 20:
            context_window.pop(0)

        file_status["chunks_done"] = i + 1
        status_files[rel] = file_status

    file_status["done"] = True
    status_files[rel] = file_status
    log_ok("arquivo concluído", project, fname)
    return "\n".join(doc_parts)


def process_project(project_path: Path):
    name = project_path.name
    log_info(f"{'='*50}", name)
    log_info(f"iniciando projeto", name)

    status = load_status(name)
    if status.get("finished_at"):
        log_skip(f"já finalizado em {status['finished_at']}", name)
        return

    profile = detect_profile(project_path)
    status["profile"] = profile["lang_label"]
    log_info(f"perfil: {profile['lang_label']} | modelo: {MODEL}", name)

    if not status["started_at"]:
        status["started_at"] = datetime.now().isoformat()

    files = sorted([
        f for ext in profile["extensions"]
        for f in project_path.rglob(f"*{ext}")
        if not any(part in profile["ignore_dirs"] for part in f.parts)
    ])

    if not files:
        log_warn(f"nenhum arquivo {profile['extensions']} encontrado", name)
        status["finished_at"] = datetime.now().isoformat()
        save_status(name, status)
        return

    log_info(f"{len(files)} arquivo(s) encontrado(s)", name)

    doc_path = DOCS_DIR / f"{name}.md"
    doc_header = (
        f"# 📦 Documentação: `{name}`\n\n"
        f"_Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} · "
        f"Perfil: **{profile['lang_label']}**_\n"
    )

    context_window: list[str] = []
    all_docs = [doc_header]
    done_count = 0

    for filepath in files:
        file_label = str(filepath.relative_to(project_path))
        log_info(f"[{done_count+1}/{len(files)}] {file_label}", name)

        doc_chunk = process_file(filepath, context_window, status["files"], profile, name)
        if doc_chunk:
            all_docs.append(doc_chunk)
            done_count += 1

        doc_path.write_text("\n".join(all_docs), encoding="utf-8")
        save_status(name, status)

    status["finished_at"] = datetime.now().isoformat()
    save_status(name, status)
    log_ok(f"projeto concluído → {doc_path}", name)


# ── Entry point ───────────────────────────────────────────────────────

def main():
    log_info("Documently iniciando...")
    log_info(f"modelo: {MODEL} | host: {OLLAMA_HOST} | max_tokens: {MAX_TOKENS}")

    wait_for_ollama()

    projects = sorted([p for p in PROJECTS_DIR.iterdir() if p.is_dir()])

    # debug: mostra o que esta montado em /projects
    log_info(f"PROJECTS_DIR = {PROJECTS_DIR} | existe: {PROJECTS_DIR.exists()}")
    if PROJECTS_DIR.exists():
        all_entries = list(PROJECTS_DIR.iterdir())
        log_info(f"entradas em /projects ({len(all_entries)}): {[e.name for e in all_entries]}")
        for entry in all_entries:
            log_info(f"  {entry.name} -> is_dir={entry.is_dir()} is_file={entry.is_file()}")
    if not projects:
        log_warn("nenhum projeto encontrado em /projects")
        return

    names = [p.name for p in projects]
    log_info(f"{len(projects)} projeto(s): {names}")

    for project in projects:
        process_project(project)

    log_ok("todos os projetos concluídos!")
    log_info(f"docs   → /output/docs/")
    log_info(f"status → /output/status/")


if __name__ == "__main__":
    main()