# GitHub — somente código e dados sintéticos

O repositório remoto não deve receber decisões reais, planilhas PGFN, GOLD, outputs de revisão ou pesos do modelo.

Antes de qualquer commit:

```powershell
git status
```

Não devem aparecer:

```text
data_private\entrada_pgfn.xlsx
runtime\
*.xlsx
*.jsonl reais
*.gguf
*.safetensors
artifacts\models\
```

Os únicos JSONL deliberadamente versionados são:

```text
data/benchmark_10.jsonl
data/benchmark_100.jsonl
```

Fluxo de código:

```powershell
git add .
git status
git commit -m "feat: local xlsx teacher gold slm pipeline"
git push
```

A planilha real é colocada somente depois do clone, diretamente na máquina institucional autorizada.
