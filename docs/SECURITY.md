# Segurança

## Benchmark sintético

Pode ser executado fora da PGFN porque não contém dados reais.

## Dados reais

- não usar APIs públicas/terceiros sem autorização institucional;
- manter `llama-server` em `127.0.0.1`;
- não abrir a porta 8081 na rede;
- não versionar inputs/resultados reais;
- não copiar decisões reais para máquina pessoal;
- revisar permissões do diretório local de trabalho.

## Quantização

O preset sintético usa uma quantização comunitária do checkpoint oficial.
Antes de uso com dados reais, a organização deve aprovar a origem/binário
ou gerar internamente uma quantização a partir dos pesos oficiais.
