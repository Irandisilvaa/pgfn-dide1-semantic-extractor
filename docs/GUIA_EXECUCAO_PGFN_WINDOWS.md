# Guia de execução — PGFN Windows — v3.1

## Entrada

A v3.1 usa arquivo XLSX local. Não usa API de planilha, token ou Spreadsheet ID.

Coloque a planilha real somente na máquina institucional autorizada:

```text
data_private\entrada_pgfn.xlsx
```

Não faça commit/push desse arquivo.

## Sequência

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
.\scripts\10_teacher_export_20.ps1
```

Depois:

```powershell
.\scripts\11_teacher_export_100.ps1
```

Somente após revisar os testes:

```powershell
.\scripts\12_teacher_export_full.ps1
```

Se interromper:

```powershell
.\scripts\13_teacher_resume_full.ps1
```

A planilha de origem é somente leitura. As saídas ficam em `runtime\private_annotations\` e são ignoradas pelo Git.
