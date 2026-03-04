"""
Code Analyzer — Loop principal
Varre /projects/*, analisa cada arquivo e grava:
  /output/docs/<projeto>.md
  /output/status/<projeto>.json
"""

import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime

# ── Configuração via env ──────────────────────────────────────────────
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL        = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:3b")
MAX_TOKENS   = int(os.getenv("MAX_TOKENS_PER_CHUNK", 3000))
EXTENSIONS   = set(os.getenv("EXTENSIONS", ".sol,.py,.js,.ts,.go,.rs").split(","))
PROJECTS_DIR = Path("/projects")
DOCS_DIR     = Path("/output/docs")
STATUS_DIR   = Path("/output/status")

DOCS_DIR.mkdir(parents=True, exist_ok=True)
STATUS_DIR.mkdir(parents=True, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────

def wait_for_ollama(retries=20, delay=3):
    """Aguarda Ollama estar pronto antes de começar."""
    print("⏳ Aguardando Ollama...")
    for i in range(retries):
        try:
            r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            if r.status_code == 200:
                print("✅ Ollama pronto!")
                return
        except Exception:
            pass
        print(f"   tentativa {i+1}/{retries}...")
        time.sleep(delay)
    raise RuntimeError("Ollama não respondeu a tempo.")


def load_status(project_name: str) -> dict:
    path = STATUS_DIR / f"{project_name}.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"project": project_name, "files": {}, "started_at": None, "finished_at": None}


def save_status(project_name: str, status: dict):
    path = STATUS_DIR / f"{project_name}.json"
    path.write_text(json.dumps(status, indent=2, ensure_ascii=False))


def chunk_text(content: str, max_tokens: int = MAX_TOKENS) -> list[str]:
    """Divide o conteúdo em chunks respeitando o limite de tokens (estimado)."""
    lines = content.splitlines(keepends=True)
    chunks, current, count = [], [], 0
    for line in lines:
        t = len(line) // 4  # ~4 chars por token
        if count + t > max_tokens and current:
            chunks.append("".join(current))
            current, count = [line], t
        else:
            current.append(line)
            count += t
    if current:
        chunks.append("".join(current))
    return chunks or [""]


def analyze_chunk(chunk: str, context_summary: str, filename: str, chunk_idx: int, total: int) -> str:
    """Envia chunk para Ollama e retorna a análise."""
    ext = Path(filename).suffix
    lang_map = {".sol": "Solidity", ".py": "Python", ".js": "JavaScript",
                ".ts": "TypeScript", ".go": "Go", ".rs": "Rust"}
    lang = lang_map.get(ext, "código")

    prompt = f"""Você é um analisador de código especialista. Analise este trecho de {lang}.

Contexto já analisado (resumo): {context_summary[-600:] if context_summary else "Nenhum — este é o início do arquivo."}

Arquivo: {filename}  (chunk {chunk_idx + 1} de {total})

```{ext.lstrip('.')}
{chunk}
```

Responda em português com:
1. **O que faz**: descrição objetiva do trecho
2. **Funções/contratos**: liste nomes e responsabilidades
3. **Atenções**: riscos, bugs potenciais ou más práticas (se houver)

Seja conciso (máx 300 palavras)."""

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

def process_file(filepath: Path, context_window: list, status_files: dict) -> str:
    """Analisa um arquivo inteiro, chunk por chunk. Retorna a doc gerada."""
    rel = str(filepath)
    file_status = status_files.get(rel, {"chunks_done": 0, "total_chunks": 0, "done": False})

    try:
        content = filepath.read_text(errors="replace")
    except Exception as e:
        return f"> ⚠️ Não foi possível ler `{filepath.name}`: {e}\n"

    chunks = chunk_text(content)
    file_status["total_chunks"] = len(chunks)
    status_files[rel] = file_status

    if file_status.get("done"):
        print(f"   ⏭  {filepath.name} já analisado, pulando.")
        return ""  # já processado em execução anterior

    doc_parts = [f"\n---\n## 📄 `{filepath.name}`\n"]
    context_summary = "\n".join(context_window[-5:])  # últimos 5 resumos

    for i, chunk in enumerate(chunks):
        if i < file_status["chunks_done"]:
            continue  # retoma de onde parou
        print(f"      chunk {i+1}/{len(chunks)}...")
        analysis = analyze_chunk(chunk, context_summary, filepath.name, i, len(chunks))
        doc_parts.append(f"### Chunk {i+1}/{len(chunks)}\n\n{analysis}\n")

        # Atualiza janela de contexto (sliding window)
        context_window.append(f"[{filepath.name} c{i+1}]: {analysis[:200]}")
        if len(context_window) > 20:
            context_window.pop(0)

        file_status["chunks_done"] = i + 1
        status_files[rel] = file_status

    file_status["done"] = True
    status_files[rel] = file_status
    return "\n".join(doc_parts)


def process_project(project_path: Path):
    name = project_path.name
    print(f"\n{'='*60}")
    print(f"🚀 Projeto: {name}")
    print(f"{'='*60}")

    status = load_status(name)
    if status.get("finished_at"):
        print(f"✅ {name} já finalizado em {status['finished_at']}. Pulando.")
        return

    if not status["started_at"]:
        status["started_at"] = datetime.now().isoformat()

    # Coleta arquivos relevantes
    files = sorted([
        f for ext in EXTENSIONS
        for f in project_path.rglob(f"*{ext}")
        if ".git" not in f.parts
    ])

    if not files:
        print(f"⚠️  Nenhum arquivo com extensões {EXTENSIONS} encontrado em {name}.")
        status["finished_at"] = datetime.now().isoformat()
        save_status(name, status)
        return

    print(f"📂 {len(files)} arquivo(s) encontrado(s)")

    doc_path = DOCS_DIR / f"{name}.md"
    doc_header = f"# 📦 Documentação: `{name}`\n\n_Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}_\n"

    context_window: list[str] = []
    all_docs = [doc_header]

    for filepath in files:
        rel = str(filepath)
        file_label = filepath.relative_to(project_path)
        print(f"\n   📄 {file_label}")

        doc_chunk = process_file(filepath, context_window, status["files"])
        if doc_chunk:
            all_docs.append(doc_chunk)

        # Salva progresso após cada arquivo
        doc_path.write_text("\n".join(all_docs), encoding="utf-8")
        save_status(name, status)
        print(f"      💾 Status salvo")

    status["finished_at"] = datetime.now().isoformat()
    save_status(name, status)
    print(f"\n✅ {name} concluído! → {doc_path}")


# ── Entry point ───────────────────────────────────────────────────────

def main():
    wait_for_ollama()

    projects = sorted([p for p in PROJECTS_DIR.iterdir() if p.is_dir()])
    if not projects:
        print("⚠️  Nenhum projeto encontrado em /projects.")
        return

    print(f"\n🔍 {len(projects)} projeto(s) encontrado(s): {[p.name for p in projects]}")

    for project in projects:
        process_project(project)

    print("\n\n🎉 Todos os projetos analisados!")
    print(f"   Docs   → /output/docs/")
    print(f"   Status → /output/status/")


if __name__ == "__main__":
    main()
