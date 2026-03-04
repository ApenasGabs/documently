from pathlib import Path

# ── Detecção de perfil ────────────────────────────────────────────────

def detect_profile(project_path: Path) -> dict:
    """Detecta o perfil do projeto pelos arquivos de configuração presentes."""
    files_in_root = {f.name for f in project_path.iterdir() if f.is_file()}

    for profile_name, profile in PROFILES.items():
        if profile_name == "fallback":
            continue
        for trigger in profile["triggers"]:
            if trigger in files_in_root:
                print(f"   🔎 Perfil detectado: {profile_name} (trigger: {trigger})")
                return profile

    print(f"   🔎 Nenhum perfil detectado, usando fallback com extensões do env.")
    return PROFILES["fallback"]


# ── Perfis por tipo de projeto ────────────────────────────────────────
PROFILES = {
    "solidity": {
        "triggers": ["hardhat.config.js", "hardhat.config.ts", "truffle-config.js", "foundry.toml", "brownie-config.yaml"],
        "extensions": [".sol"],
        "ignore_dirs": {"artifacts", "cache", "out", "node_modules", ".git"},
        "lang_label": "Solidity",
        "prompt_focus": (
            "Audite este contrato inteligente com foco em:\n"
            "- Funções públicas/externas e seus modificadores de acesso\n"
            "- Eventos emitidos e quando ocorrem\n"
            "- Riscos de segurança (reentrância, overflow, access control)\n"
            "- Padrões utilizados (Ownable, Pausable, ERC20, ERC721, etc)"
        ),
    },
    "javascript": {
        "triggers": ["package.json"],
        "extensions": [".js", ".ts", ".jsx", ".tsx"],
        "ignore_dirs": {"node_modules", "dist", ".next", "build", "coverage", ".git"},
        "lang_label": "JavaScript/TypeScript",
        "prompt_focus": (
            "Documente este código JS/TS com foco em:\n"
            "- Funções e componentes exportados\n"
            "- Tipos e interfaces relevantes\n"
            "- Efeitos colaterais, chamadas de API ou acesso a estado global\n"
            "- Dependências externas utilizadas"
        ),
    },
    "java": {
        "triggers": ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"],
        "extensions": [".java"],
        "ignore_dirs": {"target", "build", "bin", ".gradle", ".mvn", ".git"},
        "lang_label": "Java",
        "prompt_focus": (
            "Documente este código Java com foco em:\n"
            "- Classes, interfaces e responsabilidades\n"
            "- Métodos públicos e suas assinaturas\n"
            "- Anotações relevantes (Spring, JPA, etc)\n"
            "- Padrões de design identificados (singleton, factory, etc)"
        ),
    },
    "python": {
        "triggers": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
        "extensions": [".py"],
        "ignore_dirs": {"__pycache__", ".venv", "venv", "dist", ".egg-info", ".git"},
        "lang_label": "Python",
        "prompt_focus": (
            "Documente este código Python com foco em:\n"
            "- Funções e classes principais\n"
            "- Parâmetros e tipos esperados\n"
            "- Dependências externas utilizadas\n"
            "- Fluxo principal de execução"
        ),
    },
    "rust": {
        "triggers": ["Cargo.toml"],
        "extensions": [".rs"],
        "ignore_dirs": {"target", ".git"},
        "lang_label": "Rust",
        "prompt_focus": (
            "Documente este código Rust com foco em:\n"
            "- Structs, enums e traits definidos\n"
            "- Funções públicas e suas assinaturas\n"
            "- Uso de unsafe e justificativa\n"
            "- Lifetimes e ownership relevantes"
        ),
    },
    "go": {
        "triggers": ["go.mod"],
        "extensions": [".go"],
        "ignore_dirs": {"vendor", ".git"},
        "lang_label": "Go",
        "prompt_focus": (
            "Documente este código Go com foco em:\n"
            "- Pacotes e funções exportadas\n"
            "- Structs e interfaces definidas\n"
            "- Goroutines e uso de channels\n"
            "- Tratamento de erros"
        ),
    },
    "fallback": {
        "triggers": [],
        "extensions": list(set(os.getenv("EXTENSIONS", ".sol,.py,.js,.ts,.go,.rs,.java").split(","))),
        "ignore_dirs": {".git", "node_modules", "target", "build", "dist", "__pycache__"},
        "lang_label": "código",
        "prompt_focus": (
            "Analise este trecho de código e documente:\n"
            "- O que faz\n"
            "- Funções e estruturas principais\n"
            "- Riscos ou problemas encontrados"
        ),
    },
}
