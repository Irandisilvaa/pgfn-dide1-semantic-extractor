# Guia rápido — piloto v3.3

## Objetivo

Validar as proteções contra falsos positivos encontradas no piloto v3.2 antes de liberar lote de 500.

## Sequência

1. Atualizar código para `3.3.0-hard-negative-guards`.
2. Executar `pytest -q` e confirmar 37 testes aprovados.
3. Rodar `scripts/18_audit_zero_candidates_v33.ps1` para revisar os documentos sem candidato do lote v3.2.
4. Rodar `scripts/16_teacher_export_next_100_v33.ps1` para 100 decisões inéditas.
5. Revisar `teacher_review_v33_next100.xlsx`.
6. Somente depois da revisão, considerar `scripts/17_teacher_export_next_500_v33.ps1`.

## Arquivos gerados localmente

- `runtime/private_annotations/zero_candidates_v32_audit.xlsx`
- `runtime/private_annotations/teacher_review_v33_next100.xlsx`
- `runtime/private_annotations/teacher_v33_next100_checkpoint.json`

Esses arquivos podem conter dados reais e não devem ser enviados ao GitHub.
