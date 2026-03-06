"""
Documently — Hardware Profile
Detecta perfil de hardware (low/mid/high/ultra) para ajustar limites automaticamente.
"""

import os
import platform

# Perfis e limites sugeridos
PROFILES = {
    "low": {
        "OLLAMA_NUM_CTX": 2048,
        "MAX_TOKENS_PER_CHUNK": 1500,
        "TRIVIAL_LINE_THRESHOLD": 6,
        "TRIVIAL_BATCH_SIZE": 4,
    },
    "mid": {
        "OLLAMA_NUM_CTX": 4096,
        "MAX_TOKENS_PER_CHUNK": 3000,
        "TRIVIAL_LINE_THRESHOLD": 8,
        "TRIVIAL_BATCH_SIZE": 8,
    },
    "high": {
        "OLLAMA_NUM_CTX": 8192,
        "MAX_TOKENS_PER_CHUNK": 6000,
        "TRIVIAL_LINE_THRESHOLD": 12,
        "TRIVIAL_BATCH_SIZE": 12,
    },
    "ultra": {
        "OLLAMA_NUM_CTX": 16384,
        "MAX_TOKENS_PER_CHUNK": 12000,
        "TRIVIAL_LINE_THRESHOLD": 16,
        "TRIVIAL_BATCH_SIZE": 16,
    },
}

def detect_hardware_profile():
    # Permite override manual
    override = os.getenv("HARDWARE_PROFILE")
    if override in PROFILES:
        return override
    # Heurística simples: RAM + GPU
    try:
        import psutil
        ram_gb = int(psutil.virtual_memory().total / 1024 / 1024 / 1024)
    except ImportError:
        ram_gb = 8
    gpu = None
    try:
        import torch
        if torch.cuda.is_available():
            gpu = torch.cuda.get_device_properties(0).total_memory // (1024**3)
    except ImportError:
        pass
    if gpu and gpu >= 16:
        return "ultra"
    if gpu and gpu >= 8:
        return "high"
    if ram_gb >= 32:
        return "high"
    if ram_gb >= 16:
        return "mid"
    return "low"

def get_profile_vars(profile):
    return PROFILES.get(profile, PROFILES["mid"])
