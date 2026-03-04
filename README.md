# 🔍 Documently - Local Code Analyzer

Analisa e documenta repositórios de código usando IA local (Ollama) via Docker, sem enviar nada para a nuvem.

## 📁 Estrutura

```
documently/
├── docker-compose.yml        ← orquestração dos serviços (Ollama + analyzer)
├── setup.py                  ← configuração interativa (rode isso primeiro!)
├── .env                      ← gerado pelo setup.py (não suba no git)
│
├── analyzer/                 ← código do analisador
│   ├── main.py               ← loop principal: varre projetos, chama Ollama, salva docs
│   └── profiles.py           ← perfis por linguagem: triggers, extensões, prompts, ignore_dirs
│
├── projects/                 ← coloque seus projetos aqui (qualquer nome)
│   ├── meu-contrato/         ← ex: projeto Solidity (tem hardhat.config.js → perfil solidity)
│   └── outro-repo/           ← ex: projeto Java (tem pom.xml → perfil java)
│
├── docs/                     ← documentação gerada automaticamente (auto-criada)
│   ├── meu-contrato.md
│   └── outro-repo.md
│
└── status/                   ← progresso de cada projeto (auto-criado)
    ├── meu-contrato.json     ← chunks processados, status por arquivo, perfil detectado
    └── outro-repo.json
```

## 🚀 Como usar

### 1. Pré-requisitos

```bash
# Linux — Docker + Docker Compose
sudo apt install docker.io docker-compose-plugin -y
sudo usermod -aG docker $USER
# (logout e login para aplicar o grupo)

# Opcional: suporte a GPU Nvidia
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

> **Windows/Mac:** instale o [Docker Desktop](https://docs.docker.com/get-docker/)

### 2. Configure o ambiente

```bash
# Linux/Mac
python3 setup.py

# Windows
python setup.py
```

O setup detecta seu hardware automaticamente, recomenda o melhor modelo e gera o `.env`:

```
1 / 4  Detectando hardware...
  ✅ RAM detectada: 16 GB
  ✅ GPU detectada: NVIDIA RTX 3060 com 4.0 GB de VRAM

2 / 4  Recomendando modelo...
  ▶ DeepSeek Coder 6.7B (q4)
    Tamanho: ~4GB | Qualidade: ótima | Velocidade: média

  Usar este modelo? (S/n):
```

### 3. Clone seus projetos dentro de `projects/`

```bash
# O nome da pasta vira o nome da documentação gerada — use nomes descritivos
git clone https://github.com/user/meu-contrato  ./projects/meu-contrato
git clone https://github.com/user/outro-repo    ./projects/outro-repo
```

> Sem restrição de nomes ou quantidade — qualquer pasta dentro de `projects/` é analisada automaticamente.

### 4. Rode

```bash
# Primeira vez (baixa o modelo, pode demorar conforme o tamanho)
docker compose up

# Próximas vezes (retoma de onde parou)
docker compose up analyzer

# Rodar em background
docker compose up -d && docker compose logs -f analyzer
```

### 5. Acompanhe o progresso

```bash
# Status em tempo real de um projeto
watch -n 2 cat status/meu-contrato.json

# Ver a documentação sendo gerada
tail -f docs/meu-contrato.md
```

## 🔎 Detecção automática de linguagem

O analisador identifica o tipo de projeto pelos arquivos de configuração presentes e aplica um prompt especializado para cada linguagem:

| Arquivo detectado | Perfil | Foco da análise |
|---|---|---|
| `hardhat.config.*`, `foundry.toml` | Solidity | Auditoria: funções, eventos, riscos de segurança |
| `package.json` | JavaScript/TypeScript | Exports, tipos, efeitos colaterais |
| `pom.xml`, `build.gradle` | Java | Classes, métodos públicos, anotações |
| `requirements.txt`, `pyproject.toml` | Python | Funções, dependências, fluxo principal |
| `Cargo.toml` | Rust | Structs, traits, uso de unsafe |
| `go.mod` | Go | Pacotes, goroutines, tratamento de erros |
| _(nenhum)_ | Fallback | Análise geral com extensões do `.env` |

## ⚙️ Configurações (geradas pelo setup no `.env`)

| Variável | Descrição |
|---|---|
| `OLLAMA_MODEL` | Modelo a usar |
| `MAX_TOKENS_PER_CHUNK` | Tamanho dos chunks de análise |
| `EXTENSIONS` | Extensões analisadas no modo fallback |
| `OLLAMA_NUM_GPU_LAYERS` | Camadas na GPU (0 = CPU only) |

Para reconfigurar, basta rodar `python3 setup.py` novamente.

## 🤖 Modelos disponíveis

| Modelo | Tamanho | VRAM mínima | Qualidade | Velocidade |
|---|---|---|---|---|
| `qwen2.5-coder:3b` | ~2GB | CPU ok | boa | rápida |
| `deepseek-coder:6.7b-q4_K_M` | ~4GB | 4GB | ótima | média |
| `codellama:7b-q4_K_M` | ~4GB | 4GB | boa | média |
| `codellama:13b-q4_K_M` | ~8GB | 8GB | excelente | lenta |

## 🔄 Retomada automática

Se o processo for interrompido, basta rodar `docker compose up analyzer` novamente.
O progresso de cada arquivo é salvo em `status/<projeto>.json` e o loop continua exatamente de onde parou.

Para forçar uma re-análise completa de um projeto:
```bash
rm status/meu-contrato.json
```

## 📊 Formato do arquivo de status

```json
{
  "project": "meu-contrato",
  "profile": "Solidity",
  "started_at": "2024-01-15T10:30:00",
  "finished_at": null,
  "files": {
    "/projects/meu-contrato/contracts/Token.sol": {
      "chunks_done": 2,
      "total_chunks": 3,
      "done": false
    }
  }
}
```

## 🔁 Responsabilidade de cada arquivo

| Arquivo | Quando mexer |
|---|---|
| `setup.py` | Ao configurar pela primeira vez ou trocar hardware |
| `docker-compose.yml` | Raramente — portas ou recursos avançados |
| `analyzer/profiles.py` | Adicionar linguagem nova ou ajustar prompts |
| `analyzer/main.py` | Raramente — só se mudar o fluxo do loop |
| `projects/*` | Sempre — aqui ficam os repos a analisar |
| `docs/*` | Nunca — gerado automaticamente |
| `status/*` | Nunca — gerado automaticamente (delete para re-analisar) |

## 💡 Sem GPU?

O setup detecta isso automaticamente e configura o Ollama para rodar via CPU. Funciona normalmente com 16GB de RAM, apenas mais lento.