# 🔍 Documently - Local Code Analyzer

Analisa e documenta repositórios de código usando IA local (Ollama) via Docker.

## 📁 Estrutura esperada

```
documently/
├── docker-compose.yml       ← orquestração dos serviços
├── analyzer/                ← código do analisador (não mexa)
├── projects/                ← coloque seus projetos aqui
│   ├── meu-contrato/
│   └── outro-repo/
├── docs/                    ← documentação gerada (auto-criada)
│   ├── meu-contrato.md
│   └── outro-repo.md
└── status/                  ← progresso de cada projeto (auto-criado)
    ├── meu-contrato.json
    └── outro-repo.json
```

## 🚀 Como usar

### 1. Pré-requisitos
```bash
# Docker + Docker Compose
sudo apt install docker.io docker-compose-plugin -y
sudo usermod -aG docker $USER
# (logout e login para aplicar o grupo)

# Opcional: suporte a GPU Nvidia
# https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html
```

### 2. Clone seus projetos dentro de `projects/`
```bash
# O nome da pasta vira o nome da documentação gerada — use nomes descritivos
git clone https://github.com/user/meu-contrato  ./projects/meu-contrato
git clone https://github.com/user/outro-repo    ./projects/outro-repo
```

> Sem restrição de nomes ou quantidade — qualquer pasta dentro de `projects/` é analisada automaticamente.

### 3. Rode
```bash
# Primeira vez (baixa o modelo ~2GB, pode demorar)
docker compose up

# Próximas vezes (retoma de onde parou)
docker compose up analyzer

# Rodar em background
docker compose up -d && docker compose logs -f analyzer
```

### 4. Acompanhe o progresso
```bash
# Status em tempo real de um projeto
watch -n 2 cat status/meu-contrato.json

# Ver a documentação sendo gerada
tail -f docs/meu-contrato.md
```

## ⚙️ Configurações (docker-compose.yml → environment)

| Variável | Padrão | Descrição |
|---|---|---|
| `OLLAMA_MODEL` | `qwen2.5-coder:3b` | Modelo a usar |
| `MAX_TOKENS_PER_CHUNK` | `3000` | Tamanho dos chunks |
| `EXTENSIONS` | `.sol,.py,.js,.ts,.go,.rs` | Extensões analisadas |

## 🤖 Modelos disponíveis (troque no docker-compose.yml)

| Modelo | VRAM | Qualidade | Velocidade |
|---|---|---|---|
| `qwen2.5-coder:3b` | ~2GB | boa | rápida |
| `deepseek-coder:6.7b-q4_K_M` | ~4GB | ótima | média |
| `codellama:7b-q4_K_M` | ~4GB | boa (Solidity) | média |

## 🔄 Retomada automática

Se o processo for interrompido, basta rodar `docker compose up analyzer` novamente.
O progresso de cada arquivo é salvo em `status/<projeto>.json` e o loop continua exatamente de onde parou.

## 📊 Formato do arquivo de status

```json
{
  "project": "meu-contrato",
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

## 💡 Sem GPU?

Comente o bloco `deploy` no `docker-compose.yml`. O Ollama roda via CPU — mais lento, mas funciona normalmente com 16GB de RAM.