# Validação da versão com identificadores em português

Esta versão mantém a lógica do projeto e traduz para português os nomes internos de funções, classes, constantes e variáveis controlados pelo código do DIDE1.

Foram mantidos sem tradução os nomes que fazem parte de contratos externos e formatos de dados, como:

- argumentos de linha de comando (`--input`, `--output`, `--teacher`, etc.);
- variáveis de ambiente `DIDE1_LLM_*`;
- chaves JSON usadas na comunicação com o modelo (`selected`, `unit_ids`, `category`, `priority`, `reason`);
- campos técnicos já usados nos arquivos de saída (`teacher_status`, `decision_sha256`, etc.);
- nomes exigidos por bibliotecas Python de terceiros (`timeout`, `output_dir`, `model`, `args`, etc.).

Esses nomes foram preservados porque alterá-los mudaria o contrato de integração ou poderia quebrar bibliotecas externas.

## Validações executadas

- Compilação de todos os módulos Python com `compileall`.
- Suíte completa do repositório: **28 testes aprovados**.
- Execução ponta a ponta em dados sintéticos usando `--teacher rules`.
- Comparação com a versão original: `predictions.jsonl`, `errors.jsonl`, manifesto funcional e conteúdo do `review.xlsx` equivalentes.
- Simulação da chamada ao Qwen: payload HTTP e resultado equivalentes à versão original.
- Geração dos arquivos de SFT a partir de GOLD sintético: saídas equivalentes à versão original.

Nenhuma regra jurídica, categoria, prompt, critério de filtro, estrutura de saída ou fluxo de decisão foi alterado nesta refatoração.
