# Roteiro de 3 minutos

## 1. Problema

A primeira abordagem BIO encontrava fragmentos lexicalmente plausíveis,
mas nem sempre semanticamente úteis para a atuação do procurador.

## 2. Nova arquitetura

Decisão -> limpeza -> unidades semânticas -> filtros -> LLM local seleciona
IDs -> adjudicação final -> Python recupera o texto literal.

O modelo nunca redige o recorte livremente.

## 3. Baseline

Qwen2.5 1.5B em CPU:
- Precision exata: 26,32%
- Recall exato: 45,45%
- F1: 33,33%
- 2 erros estruturais em 10 documentos
- ~7 min para 10 casos

## 4. Piloto v2

Qwen3.5-9B:
- maior capacidade;
- execução local;
- JSON Schema constrained output;
- IDs restritos;
- deduplicação;
- foco explícito em distinguir “parte pediu” de “juiz determinou”.

## 5. Próximo passo

Rodar exatamente os mesmos 100 sintéticos, congelar métricas e só então
fazer uma pequena validação com decisões reais em infraestrutura PGFN,
com revisão humana.
