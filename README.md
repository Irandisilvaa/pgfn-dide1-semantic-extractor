# PGFN DIDE1 v4.2 — Router + Teacher Resiliente + Revisão Consolidada + Métricas

Pipeline local para extração/classificação semântica de decisões judiciais da defesa cível.

## Fluxo

`dados/entarda.xlsx -> regras Jovaldo -> router por contexto -> Qwen3.5-9B local -> revisão consolidada -> métricas -> GOLD -> QLoRA/SLM`

## O que esta versão incorpora
- exclusão de execução fiscal por padrão;
- regras Jovaldo determinísticas e ordenadas;
- contexto por Classe, Órgão Julgador, Expediente, Assunto, Seção/Subseção e Núcleo;
- roteamento hierárquico com fallback global;
- Qwen teacher seleciona IDs de unidades, sem reescrever o texto-fonte;
- reconstrução exata do recorte;
- JSON Schema + retry + parser tolerante;
- cache SHA-256 de decisões idênticas;
- filtros de assinatura, URL, fechos genéricos e fragmentos órfãos;
- fallback determinístico conservador;
- workbook de revisão com **uma linha por decisão única**;
- até 3 candidatos lado a lado, cada um validado separadamente;
- campos para recortes perdidos pelo teacher na mesma linha;
- aba `metricas` com precisão, taxa útil, recall estimado, F1, acurácia de categoria e cobertura documental;
- GOLD deduplicado por decisão revisada;
- `--unique-limit` para montar lotes com quantidade exata de decisões únicas.

## Segurança
A pasta `dados/`, planilhas reais, `runtime/`, JSONL de produção e modelos são ignorados pelo Git. Não versione decisões reais da PGFN.

## Instalação

Windows PGFN:

```powershell
cd C:\PGFN\DIDE1\v3.1\pgfn-dide1-semantic-extractor
.\.venv\Scripts\python.exe -m pip install . --no-deps --no-cache-dir --force-reinstall
.\.venv\Scripts\python.exe -m pytest -q
Get-Content VERSION
```

Esperado:

```text
4.3.0-review-compact
```

## Rodar 500 decisões únicas

Com o `llama-server` já ativo em `127.0.0.1:8081`:

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

`--unique-limit 500` é diferente de `--limit 500`: o primeiro busca 500 decisões únicas por SHA-256, mesmo que precise escanear mais de 500 linhas por causa de duplicatas.

## Review final

Abra:

```powershell
Start-Process .\runtime\piloto500_qwen_v42\review.xlsx
```

Aba principal: `revisao_consolidada`.

Para cada candidato, marque `APROVADO`, `AJUSTADO` ou `REJEITADO`. Uma decisão pode ter vários recortes corretos; não é necessário escolher apenas um. Depois de ler a decisão integral e registrar eventuais recortes perdidos, marque `status_documento = VALIDADO_COMPLETO`.

A aba `metricas` passa a refletir a qualidade conforme a revisão humana avança.

## Gerar GOLD

```powershell
.\.venv\Scripts\python.exe -m dide1.cli build-gold `
    --review .\runtime\piloto500_qwen_v42\review.xlsx `
    --output .\runtime\gold\gold_500.jsonl
```

Consulte `docs/V4_2_NOTAS.md` e `docs/TREINAMENTO.md`.


## v4.3 — revisão compacta

A aba `revisao` contém somente os campos necessários ao procurador. Dados de auditoria ficam em abas técnicas ocultas. Para converter um `review.xlsx` já processado na v4.2 sem rodar o Qwen novamente:

```powershell
.\scripts\rebuild_review_compact_v43.ps1
```

A base padrão do piloto Windows é `dados\entrada.xlsx`.
