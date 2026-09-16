# Persistência do modelo treinado

O treinamento foi desenhado para sobreviver a interrupções e evitar perda do modelo.

## Durante o treino

`artifacts/models/<run-name>/checkpoints/checkpoint-*` é salvo a cada `--save-steps` e o script mantém os 3 checkpoints mais recentes.

Use `--resume` / `31_resume_qlora.ps1` para retomar automaticamente do checkpoint mais recente.

## No final

O LoRA final é salvo em:

`artifacts/models/<run-name>/adapter_final/`

Também são salvos:
- tokenizer;
- `metrics.json`;
- `training_manifest.json`;
- `SHA256SUMS.json`.

## Artefato autônomo

`merge_adapter.py` mescla o adapter ao modelo-base e produz `merged_model/` em safetensors. Isso ocupa muito mais disco que o adapter.

## Backup

Git não é local para guardar pesos. Copie a pasta `artifacts/models/<run-name>/` para armazenamento institucional aprovado e verifique os hashes.
