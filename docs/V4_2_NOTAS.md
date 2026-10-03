# DIDE1 v4.2 — revisão consolidada + métricas + lote por decisão única

## Objetivo
A v4.2 transforma o `review.xlsx` em uma interface de validação humana com **uma linha por decisão única**, preservando os candidatos individualmente em colunas para que o procurador possa aprovar, ajustar ou rejeitar cada recorte sem escolher apenas um "vencedor".

## Aba `revisao_consolidada`
- uma linha por `decision_sha256`;
- `source_rows`, `expedientes` e `links_origem` mostram todas as ocorrências cobertas pela mesma decisão;
- até 3 candidatos do teacher ficam lado a lado;
- cada candidato possui `status`, `texto_ajustado`, `categoria_ajustada` e `observacao` próprios;
- três campos de `adicao_*` permitem registrar recortes perdidos pelo teacher na mesma linha;
- `status_documento=VALIDADO_COMPLETO` somente após leitura integral da decisão.

A aba `candidatos` permanece como auditoria técnica em formato longo. Ela não é mais a interface principal do procurador.

## Métricas
A aba `metricas` calcula após revisão humana:
- precisão estrita;
- taxa útil;
- recall estimado por adições humanas;
- F1 estimado;
- acurácia de categoria;
- cobertura completa por decisão;
- contagem de `RULE_FALLBACK`, `EMPTY_VALID` e `ERROR`;
- distribuição por categoria.

Antes de haver documentos `VALIDADO_COMPLETO`, esses indicadores não devem ser usados para afirmar qualidade do modelo.

## 500 decisões únicas
Use `--unique-limit 500`, não `--limit 500`. Assim, duplicatas encontradas antes da 500ª decisão única podem ser aproveitadas pelo cache, mas o workbook final terá 500 decisões únicas para revisão (salvo fim da base ou exclusões).

No Windows PGFN:

```powershell
.\scripts\run_500_windows_v42.ps1
```

Ou manualmente:

```powershell
.\.venv\Scripts\python.exe -m dide1.cli run `
    --input .\dados\entarda.xlsx `
    --start-index 0 `
    --unique-limit 500 `
    --teacher llama `
    --max-candidates 3 `
    --output .\runtime\piloto500_qwen_v42
```

## Ajustes de qualidade derivados do piloto de 100
- fechos numerados como `9. Intimações e providências necessárias.` passam a ser rejeitados;
- `3. Intimem-se.` isolado passa a ser rejeitado;
- fallback determinístico ficou mais conservador para evitar selecionar narrativa histórica;
- se o teacher falhar e nenhuma unidade segura for encontrada, o caso vira `RULE_FALLBACK_EMPTY` em vez de forçar falso positivo.
