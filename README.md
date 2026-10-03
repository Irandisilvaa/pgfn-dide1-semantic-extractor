# PGFN DIDE1 v4.1 — Router + Teacher Resiliente + GOLD

Pipeline local para extração/classificação semântica de decisões judiciais da defesa cível.

## Fluxo

`dados/base_consolidada.xlsx -> regras Jovaldo -> router por contexto -> Qwen3.5-9B local -> revisão humana -> GOLD -> QLoRA/SLM`

### O que esta versão incorpora
- exclusão de execução fiscal por padrão;
- fórmula de pré-automação da equipe transformada em `RuleEngine` determinístico e ordenado;
- contexto por Classe, Órgão Julgador, Expediente, Assunto, Seção/Subseção e Núcleo;
- roteamento hierárquico com fallback global;
- Qwen teacher seleciona IDs de unidades, não escreve o recorte livremente;
- reconstrução exata do texto-fonte;
- filtros contra pedidos da parte, referências históricas, IDs e fragmentos órfãos;
- workbook de revisão completa por procurador;
- geração de GOLD somente para documentos `VALIDADO_COMPLETO`;
- estrutura pronta para medir quando adapters QLoRA por grupo/vara passam a valer a pena.


## Novidades v4.1
- parser tolerante a `{"selected": [...]}` e `[...]`;
- saída estruturada por JSON Schema quando suportada pelo `llama-server`, com fallback compatível;
- retry automático de resposta inválida;
- fallback determinístico de regras sem derrubar o documento;
- filtros para assinatura/data/URL e fechos genéricos;
- preservação de ordem-mãe terminada em `:` quando seguida de lista;
- cache SHA-256 de decisões idênticas para consistência e economia de GPU;
- auditoria por `teacher_status`, `cache_hit`, tentativas e modo de resposta;
- manifesto com `unique_inferences`, `cache_hits`, `rule_fallbacks` e erros recuperados.

## Segurança
A pasta `dados/` e todas as planilhas são ignoradas pelo Git. Não versione decisões reais.

## Instalação rápida
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
pytest -q
```

## Smoke test sem LLM
```bash
python -m dide1.cli inspect --input dados/base_consolidada.xlsx
python -m dide1.cli run --input dados/base_consolidada.xlsx --limit 20 --teacher rules --output runtime/piloto20_rules
```

## Teacher Qwen local
Com `llama-server` em `http://127.0.0.1:8081`:
```bash
python -m dide1.cli run --input dados/base_consolidada.xlsx --limit 20 --teacher llama --output runtime/piloto20_qwen
```

## Depois da revisão humana
Consulte `docs/TREINAMENTO.md` para construir SFT por Processo e treinar QLoRA sem gerar texto livre.
