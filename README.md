# DIDE1 — Piloto Local v2.0.0

Pipeline extrativo para testar modelos locais em decisões judiciais sintéticas.

## Modelo principal

**Qwen3.5-9B, Q4_K_M**, servido localmente por `llama.cpp`.

Motivos práticos:
- 9B parâmetros;
- licença Apache 2.0 no modelo base;
- suporte multilíngue amplo;
- quantização ~6 GB, compatível com RTX 3060 12 GB;
- boa folga de VRAM para contexto;
- execução 100% local;
- saída JSON limitada por JSON Schema no próprio decoder.

## O que mudou em relação à baseline 1.5B

1. Modelo maior e mais recente.
2. JSON Schema constrained output — elimina a dependência de “o modelo lembrar de escrever JSON”.
3. IDs válidos são enumerados no schema — o modelo não pode inventar IDs.
4. Deduplicação por texto normalizado.
5. Regras mais fortes contra narrativa de relatório/fundamentação.
6. Pipeline simplificado: seleção por chunk + adjudicação final.
7. Métricas incluem Hit@1, taxa de documentos com GOLD, erros e wall time.
8. GOLD de categoria revisado individualmente por recorte.

## Segurança

Este repositório:
- não usa `.env`;
- não usa API da planilha;
- não contém decisões reais;
- não chama API externa de LLM;
- aceita o servidor de inferência apenas em `127.0.0.1/localhost`.

## Fedora / Linux CPU

```bash
./scripts/linux/01_setup.sh
./scripts/linux/02_start_qwen35_9b_cpu.sh
```

Em outro terminal:

```bash
./scripts/linux/04_health.sh
./scripts/linux/05_run_10.sh
```

> Em notebook de 8 GB, o 9B Q4 pode usar swap e ficar muito lento.
> O alvo de piloto é a RTX 3060 12 GB / 32 GB RAM.

## Linux com NVIDIA

```bash
./scripts/linux/03_start_qwen35_9b_cuda.sh
```

## Windows + RTX 3060

```powershell
.\scripts\windows\00_check_machine.ps1
.\scripts\windows\01_setup.ps1
.\scripts\windows\02_start_qwen35_9b_cuda.ps1
```

Em outro PowerShell:

```powershell
.\scripts\windows\03_run_10.ps1
```

Depois:

```powershell
.\scripts\windows\04_run_100.ps1
```

## Resultado

Arquivos em `runtime/`:
- `summary_*.json`
- `results_*.jsonl`
- `summary_*.md`

## Piloto privado local posterior

Há um runner sem API:

```bash
python -m src.pilot_private_local \
  --input /CAMINHO/LOCAL/entrada.jsonl \
  --output /CAMINHO/LOCAL/saida.jsonl
```

Formato de entrada:

```json
{"id":"ID-LOCAL","decisao":"texto da decisão"}
```

Para dados reais, execute somente em infraestrutura institucional autorizada.
