# Runbook DIDE1 v4.2

## Saídas
- `review.xlsx`: revisão humana consolidada.
- `predictions.jsonl`: candidatos em formato longo para auditoria.
- `errors.jsonl`: falhas técnicas e recuperações/fallbacks.
- `manifest.json`: parâmetros, contagens, cache e tempo.

## Workbook
### `revisao_consolidada`
Interface principal. Uma linha por decisão única (`decision_sha256`). Duplicatas da base aparecem em `source_rows`, `expedientes` e `ocorrencias_na_base`.

Cada candidato é independente:
- `candidate_N_text`
- `candidate_N_category`
- `candidate_N_status`
- `candidate_N_texto_ajustado`
- `candidate_N_categoria_ajustada`

O procurador pode aprovar mais de um recorte da mesma decisão.

### `metricas`
Calcula os indicadores após revisão humana. Antes de documentos `VALIDADO_COMPLETO`, não usar os percentuais como avaliação final do modelo.

### `decisoes` e `candidatos`
Auditoria técnica em formato longo.

## Critério de GOLD
1. Ler a decisão integral.
2. Revisar todos os candidatos.
3. Registrar recortes perdidos em `adicao_1..3` (ou `adicoes_gold` para extras).
4. Marcar `VALIDADO_COMPLETO`.
5. Executar `build-gold`.

## Lotes por decisão única
Use `--unique-limit N` quando a meta for N decisões efetivamente revisáveis. `--limit N` limita linhas da planilha e pode produzir menos decisões únicas por causa de duplicatas.
