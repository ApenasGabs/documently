"""
Documently — Frameworks
Detecção determinística e fallback IA para frameworks.
"""

import os
from pathlib import Path
from analyzer import call_ollama

def detect_framework(project_path: Path, profile: dict) -> str:
    """
    Detecta framework por arquivos/dependências (determinístico) ou IA (fallback).
    """
    # Determinístico por arquivos comuns
    files = {f.name for f in project_path.iterdir() if f.is_file()}
    # Exemplos: React, Vite, Angular, Maven, Gradle, Android
    if "package.json" in files:
        pkg = (project_path / "package.json").read_text(errors="replace")
        if '"react"' in pkg:
            return "React"
        if '"vite"' in pkg:
            return "Vite"
        if '"angular"' in pkg:
            return "Angular"
    if "pom.xml" in files:
        return "Maven"
    if "build.gradle" in files or "build.gradle.kts" in files:
        return "Gradle"
    if "AndroidManifest.xml" in files:
        return "Android"
    # Fallback IA
    try:
        prompt = (
            f"Analise a estrutura e arquivos do projeto a seguir e identifique o framework principal.\n"
            f"Arquivos: {sorted(list(files))}\n"
            f"Se não for possível determinar, responda apenas 'unknown'."
        )
        result = call_ollama(prompt, num_predict=128)
        fw = result.strip().split()[0]
        if fw.lower() in {"react", "vite", "angular", "maven", "gradle", "android"}:
            return fw.capitalize()
        return "unknown"
    except Exception:
        return "unknown"
