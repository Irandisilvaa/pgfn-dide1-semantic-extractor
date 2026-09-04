# Guia de execução — Windows — PGFN

## 1. Clonar o repositório

Use repositório privado/institucional autorizado.

```powershell
git clone <URL_DO_REPOSITORIO>
cd pgfn-dide1-semantic-extractor
```

## 2. Liberar scripts PowerShell apenas para a sessão atual

Se a política da máquina permitir:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

Isso não altera permanentemente a política da máquina.

## 3. Conferir hardware

```powershell
.\scripts\00_check_machine.ps1
```

Anote especialmente:

```powershell
nvidia-smi
```

Modelo da GPU e VRAM definem qual GGUF usar.

## 4. Python

Recomendado: Python 3.12.

Depois:

```powershell
.\scripts\01_setup_python.ps1
```

O script cria `.venv`.

## 5. Configurar `.env`

```powershell
Copy-Item .env.example .env
notepad .env
```

Exemplo:

```env
SPREADSHEET_API_BASE_URL="..."
SPREADSHEET_API_TOKEN="..."

LOCAL_LLM_BASE_URL="http://127.0.0.1:8081/v1"

LLAMA_SERVER_BIN="C:\PGFN\DIDE1\llama\llama-server.exe"
MODEL_PATH="C:\PGFN\DIDE1\models\modelo-instruct.gguf"

LLAMA_PORT="8081"
LLAMA_CTX="8192"
LLAMA_THREADS="8"
LLAMA_GPU_LAYERS="999"
LLAMA_PARALLEL="1"
```

Nunca faça commit do `.env`.

## 6. llama.cpp no Windows

A forma mais simples é usar o pacote Windows/CUDA aprovado pela instituição
contendo `llama-server.exe` e suas DLLs.

Mantenha todos os arquivos do pacote juntos, por exemplo:

```text
C:\PGFN\DIDE1\llama\
    llama-server.exe
    *.dll
```

Não copie somente o `.exe` se a distribuição trouxer DLLs.

## 7. Modelo

Coloque o GGUF localmente:

```text
C:\PGFN\DIDE1\models\modelo-instruct.gguf
```

Na inferência não use `-hf`. O script usa `-m` apontando para esse arquivo.

## 8. Subir o LLM

Terminal 1:

```powershell
.\scripts\02_start_llama_local.ps1
```

Esperado:

```text
listening on http://127.0.0.1:8081
```

Não use `0.0.0.0`.

## 9. Testar

Terminal 2:

```powershell
.\scripts\03_test_local_llm.ps1
```

Depois:

```powershell
.\scripts\04_check_llama_network.ps1
```

O servidor deve escutar em `127.0.0.1`.

## 10. Teste 10

```powershell
.\scripts\run_10.ps1
```

Arquivos:

```text
runtime\summary_10.json
runtime\preview_10.jsonl
```

## 11. Teste 100

```powershell
.\scripts\run_100.ps1
```

## 12. Escada de validação

```powershell
.\scripts\run_10.ps1
.\scripts\run_100.ps1
.\scripts\run_500.ps1
.\scripts\run_1000.ps1
```

Ou:

```powershell
.\scripts\run_sample.ps1 -N 250
```

## 13. Base completa

Somente após validar qualidade:

```powershell
.\scripts\run_full_readonly.ps1
```

Checkpoint:

```text
runtime\checkpoint_full.json
```

Se interromper:

```powershell
.\scripts\resume_full_readonly.ps1
```

## 14. Importante

A versão v1.0.1 é SOMENTE LEITURA.

Ela não altera:
- Recortes
- Ind.
- tags
- Decisão

A etapa de escrita deve ser habilitada somente depois da validação humana.
