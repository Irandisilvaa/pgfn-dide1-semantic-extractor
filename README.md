# PGFN DIDE1 v4 — Router + Teacher + GOLD

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
