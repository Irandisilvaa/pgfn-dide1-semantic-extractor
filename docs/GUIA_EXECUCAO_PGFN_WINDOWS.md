# Guia de execução — PGFN Windows — v3.2

## Entrada

A v3.2 usa arquivo XLSX local. Não usa API de planilha, token ou Spreadsheet ID.

Coloque a planilha real somente na máquina institucional autorizada:

```text
data_private\entrada_pgfn.xlsx
```

Não faça commit/push desse arquivo.

## Atualização da v3.2

A v3.2 reforça filtros observados no primeiro piloto real:

- pedido da parte x decisão atual;
- decisão atual x referência a decisão anterior;
- rejeição de prazo/comando órfão;
- melhor precedência de categorias;
- score heurístico tratado apenas como sinal auxiliar.

Nenhum dado real do piloto é versionado no GitHub.

## Sequência base

```powershell
.\scripts\01_setup_python.ps1
.\scripts\09_validate_input_xlsx.ps1
```

Terminal 1:

```powershell
.\scripts\02_start_llama_local.ps1
```

Terminal 2:

```powershell
.\scripts\03_test_local_llm.ps1
```

## Novo lote de validação da v3.2

Se o primeiro lote de 100 já foi processado, rode 100 decisões novas. O script tenta ler automaticamente a próxima linha do checkpoint anterior:

```powershell
.\scripts\14_teacher_export_next_100_v32.ps1
```

Saída:

```text
runtime\private_annotations\teacher_review_v32_next100.xlsx
```

Se necessário, você ainda pode forçar outra linha inicial:

```powershell
.\scripts\14_teacher_export_next_100_v32.ps1 -StartExcelRow 102
```

## Etapa seguinte

Somente depois de revisar o novo lote de 100:

```powershell
.\scripts\15_teacher_export_next_500_v32.ps1
```

Somente após revisar os testes e definir o protocolo humano, use o processamento integral:

```powershell
.\scripts\12_teacher_export_full.ps1
```

Se interromper o integral:

```powershell
.\scripts\13_teacher_resume_full.ps1
```

A planilha de origem é somente leitura. As saídas ficam em `runtime\private_annotations\` e são ignoradas pelo Git.
