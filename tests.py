"""
Documently — Testes unitários
Cobre as funções críticas sem precisar do Docker ou Ollama rodando.

Rodar:
  python3 tests.py
  python3 tests.py -v
"""

import sys
import types
import unittest
import importlib
import tempfile
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────
ROOT_DIR     = Path(__file__).parent
ANALYZER_DIR = ROOT_DIR / "analyzer"

# Carrega analyzer/analyzer.py como módulo com nome único para evitar
# conflito com o diretório analyzer/ que o Python trata como pacote
def load_module(name: str, path: Path):
    spec   = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

# Carrega os módulos do analyzer/ explicitamente pelo caminho
_logger   = load_module("logger",   ANALYZER_DIR / "logger.py")
_profiles = load_module("profiles", ANALYZER_DIR / "profiles.py")
_analyzer = load_module("analyzer_core", ANALYZER_DIR / "analyzer.py")
_setup    = load_module("setup_module",  ROOT_DIR   / "setup.py")

# Atalhos para uso nos testes
PROFILES      = _profiles.PROFILES
detect_profile = _profiles.detect_profile
chunk_text     = _analyzer.chunk_text
build_tree     = _analyzer.build_tree
recommend_model = _setup.recommend_model
generate_env    = _setup.generate_env
MODELS          = _setup.MODELS


# ── Helpers ───────────────────────────────────────────────────────────

def make_project(files: list[str]) -> Path:
    tmp = Path(tempfile.mkdtemp())
    for f in files:
        p = tmp / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"// conteúdo de {f}")
    return tmp


# ══════════════════════════════════════════════════════════════════════
# 1. detect_profile
# ══════════════════════════════════════════════════════════════════════

class TestDetectProfile(unittest.TestCase):

    def test_solidity_hardhat(self):
        self.assertEqual(detect_profile(make_project(["hardhat.config.js"]))["lang_label"], "Solidity")

    def test_solidity_foundry(self):
        self.assertEqual(detect_profile(make_project(["foundry.toml"]))["lang_label"], "Solidity")

    def test_javascript_package(self):
        self.assertEqual(detect_profile(make_project(["package.json"]))["lang_label"], "JavaScript/TypeScript")

    def test_java_maven(self):
        self.assertEqual(detect_profile(make_project(["pom.xml"]))["lang_label"], "Java")

    def test_java_gradle(self):
        self.assertEqual(detect_profile(make_project(["build.gradle"]))["lang_label"], "Java")

    def test_python_requirements(self):
        self.assertEqual(detect_profile(make_project(["requirements.txt"]))["lang_label"], "Python")

    def test_python_pyproject(self):
        self.assertEqual(detect_profile(make_project(["pyproject.toml"]))["lang_label"], "Python")

    def test_rust_cargo(self):
        self.assertEqual(detect_profile(make_project(["Cargo.toml"]))["lang_label"], "Rust")

    def test_go_mod(self):
        self.assertEqual(detect_profile(make_project(["go.mod"]))["lang_label"], "Go")

    def test_fallback_no_trigger(self):
        self.assertEqual(detect_profile(make_project(["README.md"])), PROFILES["fallback"])

    def test_solidity_priority_over_js(self):
        """Projetos Hardhat têm package.json E hardhat.config.js — deve detectar Solidity."""
        self.assertEqual(
            detect_profile(make_project(["package.json", "hardhat.config.js"]))["lang_label"],
            "Solidity"
        )

    def test_all_profiles_have_required_keys(self):
        required = {"triggers", "extensions", "ignore_dirs", "lang_label", "prompt_focus"}
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                missing = required - profile.keys()
                self.assertFalse(missing, f"Perfil '{name}' faltando: {missing}")


# ══════════════════════════════════════════════════════════════════════
# 2. chunk_text
# ══════════════════════════════════════════════════════════════════════

class TestChunkText(unittest.TestCase):

    def test_small_file_single_chunk(self):
        chunks = chunk_text("linha 1\nlinha 2\nlinha 3", max_tokens=1000)
        self.assertEqual(len(chunks), 1)

    def test_large_file_splits(self):
        content = "\n".join([f"linha {i:03d}" for i in range(100)])
        self.assertGreater(len(chunk_text(content, max_tokens=10)), 1)

    def test_no_content_loss(self):
        content = "\n".join([f"linha {i}" for i in range(200)])
        chunks  = chunk_text(content, max_tokens=50)
        self.assertEqual("".join(chunks).strip(), content.strip())

    def test_empty_returns_one_chunk(self):
        chunks = chunk_text("", max_tokens=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], "")

    def test_single_long_line_stays_one_chunk(self):
        self.assertEqual(len(chunk_text("x" * 10000, max_tokens=10)), 1)

    def test_chunks_respect_max_tokens(self):
        content    = "\n".join(["a" * 40] * 100)
        max_tokens = 50
        for i, chunk in enumerate(chunk_text(content, max_tokens)):
            self.assertLess(len(chunk) // 4, max_tokens * 2,
                f"Chunk {i} muito grande (~{len(chunk)//4} tokens)")


# ══════════════════════════════════════════════════════════════════════
# 3. recommend_model
# ══════════════════════════════════════════════════════════════════════

class TestRecommendModel(unittest.TestCase):

    def _rec(self, ram_gb, vram_gb=0, has_gpu=True):
        gpu = {"found": has_gpu, "vram_gb": vram_gb, "name": "Test"} if has_gpu else {"found": False}
        return recommend_model(ram_gb, gpu)

    def test_cpu_only_low_ram(self):
        self.assertEqual(self._rec(8, has_gpu=False)["id"], "qwen2.5-coder:3b")

    def test_2gb_vram(self):
        self.assertEqual(self._rec(8, vram_gb=2)["id"], "qwen2.5-coder:3b")

    def test_4gb_vram(self):
        self.assertEqual(self._rec(12, vram_gb=4)["id"], "qwen2.5-coder:7b")

    def test_never_exceeds_vram(self):
        for vram in [2, 4, 6, 8, 12]:
            gpu   = {"found": True, "vram_gb": vram, "name": "Test"}
            model = recommend_model(16, gpu)
            self.assertLessEqual(model["min_vram"], vram,
                f"{vram}GB VRAM → recomendou {model['id']} que precisa {model['min_vram']}GB")

    def test_never_exceeds_ram(self):
        for ram in [8, 12, 16, 32]:
            model = recommend_model(ram, {"found": False})
            self.assertLessEqual(model["min_ram"], ram,
                f"{ram}GB RAM → recomendou {model['id']} que precisa {model['min_ram']}GB")

    def test_fallback_minimal_hw(self):
        self.assertEqual(self._rec(4, has_gpu=False)["id"], "qwen2.5-coder:3b")


# ══════════════════════════════════════════════════════════════════════
# 4. generate_env
# ══════════════════════════════════════════════════════════════════════

class TestGenerateEnv(unittest.TestCase):

    def setUp(self):
        self.model = MODELS[0]

    def test_required_keys(self):
        config = generate_env(self.model, {"found": False})
        for key in ["OLLAMA_MODEL", "MAX_TOKENS_PER_CHUNK", "EXTENSIONS",
                    "OLLAMA_NUM_GPU_LAYERS", "OLLAMA_NUM_PARALLEL", "OLLAMA_MAX_LOADED_MODELS"]:
            self.assertIn(key, config)

    def test_gpu_layers_zero_without_gpu(self):
        self.assertEqual(generate_env(self.model, {"found": False})["OLLAMA_NUM_GPU_LAYERS"], "0")

    def test_gpu_layers_positive_with_gpu(self):
        config = generate_env(self.model, {"found": True, "vram_gb": 4.0, "name": "Test"})
        self.assertGreater(int(config["OLLAMA_NUM_GPU_LAYERS"]), 0)

    def test_gpu_layers_capped_at_35(self):
        config = generate_env(self.model, {"found": True, "vram_gb": 80.0, "name": "A100"})
        self.assertLessEqual(int(config["OLLAMA_NUM_GPU_LAYERS"]), 35)

    def test_extensions_format(self):
        config = generate_env(self.model, {"found": False})
        for ext in config["EXTENSIONS"].split(","):
            self.assertTrue(ext.startswith("."), f"Extensão inválida: '{ext}'")


# ══════════════════════════════════════════════════════════════════════
# 5. ignore_dirs
# ══════════════════════════════════════════════════════════════════════

class TestIgnoreDirs(unittest.TestCase):

    def test_java_ignores_target(self):
        self.assertIn("target", PROFILES["java"]["ignore_dirs"])

    def test_js_ignores_node_modules(self):
        self.assertIn("node_modules", PROFILES["javascript"]["ignore_dirs"])

    def test_solidity_ignores_artifacts(self):
        self.assertIn("artifacts", PROFILES["solidity"]["ignore_dirs"])

    def test_rust_ignores_target(self):
        self.assertIn("target", PROFILES["rust"]["ignore_dirs"])

    def test_python_ignores_venv(self):
        self.assertIn("venv", PROFILES["python"]["ignore_dirs"])

    def test_python_ignores_pycache(self):
        self.assertIn("__pycache__", PROFILES["python"]["ignore_dirs"])

    def test_all_profiles_ignore_git(self):
        for name, profile in PROFILES.items():
            if name == "fallback":
                continue
            with self.subTest(profile=name):
                self.assertIn(".git", profile["ignore_dirs"],
                    f"Perfil '{name}' não ignora .git")


# ══════════════════════════════════════════════════════════════════════
# 6. build_tree
# ══════════════════════════════════════════════════════════════════════

class TestBuildTree(unittest.TestCase):

    def _tree(self, files: list[str], lang="javascript") -> str:
        return build_tree(make_project(files), PROFILES[lang])

    def test_root_line_ends_with_slash(self):
        tree = self._tree(["src/index.js"])
        self.assertTrue(tree.splitlines()[0].endswith("/"))

    def test_contains_filenames(self):
        tree = self._tree(["src/index.js", "src/app.js"])
        self.assertIn("index.js", tree)
        self.assertIn("app.js", tree)

    def test_excludes_ignored_dirs(self):
        tree = self._tree(["src/index.js", "node_modules/lib.js"])
        self.assertNotIn("node_modules", tree)

    def test_shows_nested_structure(self):
        tree = self._tree(["src/components/Button.js"])
        self.assertIn("src", tree)
        self.assertIn("Button.js", tree)

    def test_empty_project_returns_root_only(self):
        tree = self._tree([])
        self.assertEqual(len(tree.splitlines()), 1)


# ══════════════════════════════════════════════════════════════════════
# Runner
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Documently — Testes Unitários\n")
    suite  = unittest.TestSuite()
    loader = unittest.TestLoader()
    for cls in [TestDetectProfile, TestChunkText, TestRecommendModel,
                TestGenerateEnv, TestIgnoreDirs, TestBuildTree]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    verbosity = 2 if "-v" in sys.argv else 1
    result    = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    print(f"\n{'✅ Todos os testes passaram!' if result.wasSuccessful() else '❌ Falhas encontradas.'}")
    sys.exit(0 if result.wasSuccessful() else 1)