# Runbook

A progressão recomendada é 20 -> +100 -> +1.000 -> restante até 10.000 decisões, com revisão entre etapas.

## Saídas de cada execução
- `review.xlsx`: planilha para procuradores.
- `predictions.jsonl`: candidatos estruturados.
- `errors.jsonl`: erros técnicos.
- `manifest.json`: parâmetros e tempo.

## Revisão humana
No `review.xlsx`:
1. Procurador lê a decisão inteira na aba `decisoes`.
2. Marca cada candidato em `candidatos`: APROVADO/AJUSTADO/REJEITADO.
3. Adiciona qualquer trecho perdido na aba `adicoes_gold`.
4. Só depois marca `status_documento=VALIDADO_COMPLETO`.

## GOLD
`python -m dide1.cli build-gold --review runtime/.../review.xlsx --output runtime/gold/gold.jsonl`
