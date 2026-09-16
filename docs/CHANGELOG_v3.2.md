# v3.2.0 — real-pilot-filters

Atualização orientada pelos padrões de erro identificados no primeiro piloto real, sem incluir dados reais no repositório.

## Correções

- Rejeição conservadora de itens enumerados que aparentam ser pedido da parte, não comando atual do juízo.
- Rejeição de referências claras a decisão/sentença anterior identificada por `id`.
- Rejeição de prazo isolado e comandos genéricos sem conteúdo semântico suficiente.
- Rejeição de ordem interna genérica de mero impulsionamento do feito.
- Precedência de `resultado_julgamento` sobre `tutela` quando o trecho contém resultado final claro.
- Reconhecimento de contrarrazões, remessa ao TRF, reexame, trânsito e arquivamento como `recurso_proximo_passo`.
- Promoção de decisum textual claro para seção `DISPOSITIVO` mesmo quando a segmentação herdou outra seção.
- Prompt final reforçado para não tratar `heuristic_score` como confiança probabilística.

## Novo teste real

- `scripts/14_teacher_export_next_100_v32.ps1`: 100 decisões novas a partir da próxima linha registrada no checkpoint anterior; fallback na linha Excel 102.
- `scripts/15_teacher_export_next_500_v32.ps1`: lote seguinte de 500, somente após revisão do novo lote de 100.

## Validação local do código

- 25 testes automatizados aprovados.
- Nenhuma planilha real ou saída privada incluída no pacote.
