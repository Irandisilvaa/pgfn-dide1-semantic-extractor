# GOLD -> SFT -> QLoRA

Não treine antes de existir GOLD humano suficiente.

## 1. Construir GOLD
```bash
python -m dide1.cli build-gold --review runtime/piloto100/review.xlsx --output runtime/gold/gold.jsonl
```

## 2. Construir dataset SFT
O builder:
- exige GOLD extrativo (trecho precisa existir literalmente na decisão);
- converte recortes para IDs das unidades-fonte;
- separa train/val/test por `Processo`, usando hash estável;
- nunca mistura decisões do mesmo processo entre splits;
- gera arquivo de issues para correção humana.

```bash
python -m dide1.training.build_sft --gold runtime/gold/gold.jsonl --outdir runtime/sft
```

## 3. QLoRA
Instale dependências de treino somente na máquina GPU:
```powershell
.\.venv-train\Scripts\python.exe -m pip install -r requirements-train.txt
```

Treino (exemplo; troque `--base-model` por caminho/modelo aprovado):
```powershell
.\.venv-train\Scripts\python.exe -m dide1.training.train_qlora `
  --base-model C:\PGFN\DIDE1\models\BASE_SLM `
  --train runtime\sft\sft_train.jsonl `
  --val runtime\sft\sft_val.jsonl `
  --output artifacts\models\dide1-slm-v1
```

## Gate para especialistas por vara/grupo
Não criar adapter específico só porque existe uma vara. Criar somente quando:
1. houver volume suficiente no GOLD;
2. o desempenho do global for consistentemente pior naquele grupo;
3. validação separada mostrar ganho real de F1/recall;
4. o ganho justificar manutenção adicional.
