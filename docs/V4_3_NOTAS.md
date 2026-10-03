# DIDE1 v4.3 — revisão compacta

Objetivo: reduzir a complexidade da revisão humana sem perder nenhum dado necessário para GOLD, treinamento ou auditoria.

## Interface principal

A aba `revisao` mostra somente:
- identificação/contexto essencial;
- até 3 recortes do teacher;
- categoria editável em dropdown;
- validação em dropdown (`PENDENTE`, `APROVADO`, `AJUSTADO`, `REJEITADO`);
- até 2 recortes ausentes adicionados pelo humano;
- status final do documento, revisor e observação.

O procurador edita diretamente `Recorte N` e/ou `Categoria N` quando marcar `AJUSTADO`. O texto/categoria originais do teacher ficam preservados em `dados_tecnicos`.

## Abas

- `revisao`: interface principal e compacta.
- `leitura_decisoes`: decisão integral para leitura, separada da grade de revisão.
- `metricas`: precisão, taxa útil, recall estimado, F1 e cobertura após revisão.
- `instrucoes`: fluxo curto de uso.
- `adicoes_gold`: casos raros com mais de 2 recortes perdidos.
- `dados_tecnicos`, `candidatos_tecnicos`, `listas`: ocultas; não editar.

## Reaproveitar lote já processado

Não precisa rodar Qwen novamente:

```powershell
.\scripts\rebuild_review_compact_v43.ps1
```

ou:

```powershell
.\.venv\Scripts\python.exe -m dide1.cli rebuild-review `
  --review .\runtime\piloto500_qwen_v42\review.xlsx `
  --output .\runtime\piloto500_qwen_v42\review_compacto_v43.xlsx
```

## GOLD seguro

`build-gold` bloqueia um documento marcado como `VALIDADO_COMPLETO` se ainda existir candidato `PENDENTE` ou categoria inválida. Os bloqueios são escritos em `gold_build_issues.csv`.
