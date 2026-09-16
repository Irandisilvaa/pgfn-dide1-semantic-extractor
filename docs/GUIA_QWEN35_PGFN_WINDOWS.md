# Qwen3.5-9B local — PGFN Windows

A v3.1 não usa `.env`.

## Servidor

```powershell
.\scripts\02_start_llama_local.ps1
```

Padrões:

```text
C:\PGFN\DIDE1\llama\llama-server.exe
C:\PGFN\DIDE1\models\Qwen3.5-9B-Q4_K_M.gguf
127.0.0.1:8081
contexto 8192
GPU layers 999
reasoning off quando suportado
```

## Teste

Em outro PowerShell:

```powershell
.\scripts\03_test_local_llm.ps1
.\scripts\04_check_llama_network.ps1
```

## Entrada real

O teacher lê `data_private\entrada_pgfn.xlsx` localmente. Não existe chamada de API de planilha.
