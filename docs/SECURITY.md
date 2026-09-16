# Segurança — v3.1 Local XLSX → Teacher → GOLD → SLM

1. O teacher roda somente em `127.0.0.1/localhost`.
2. A planilha fonte é um XLSX local e é aberta em modo read-only.
3. Esta versão não usa API de planilha, token de planilha ou Spreadsheet ID.
4. `tags` e `Ind.` são preservados para revisão humana, mas não entram na inferência do teacher.
5. A planilha real deve ficar em `data_private/` ou em outro caminho local institucional autorizado.
6. Planilhas reais, planilhas de revisão, GOLD, datasets de treino, checkpoints e pesos não devem ser commitados/pushados para GitHub.
7. GitHub deve transportar apenas código, documentação e datasets sintéticos deliberadamente públicos/versionáveis.
8. O modelo treinado deve ser copiado para armazenamento institucional aprovado.
9. Hashes SHA-256 são gerados para o adapter final e para o modelo mesclado.
