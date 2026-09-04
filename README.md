# PGFN DIDE1 — Semantic Extractor v1.0.1 — Windows

Pipeline local para seleção de recortes semanticamente acionáveis em decisões judiciais.

## Ambiente-alvo

- Windows 10/11 ou Windows Server;
- GPU local da PGFN;
- `llama-server.exe` local;
- modelo GGUF local;
- API da planilha já utilizada no ambiente;
- Python local;
- nenhum serviço externo de LLM.

## Segurança

- o cliente recusa LLM que não esteja em `127.0.0.1`/`localhost`;
- o `llama-server.exe` é iniciado em `127.0.0.1`;
- o modelo é carregado por `-m` a partir do disco;
- quando suportado pela versão instalada, o script ativa `--offline`;
- `.env`, `runtime/` e `*.gguf` são ignorados pelo Git;
- esta versão não escreve na planilha.

## Início rápido

No PowerShell:

```powershell
Copy-Item .env.example .env
.\scripts\00_check_machine.ps1
.\scripts\01_setup_python.ps1
```

Terminal 1:

```powershell
.\scripts\02_start_llama_local.ps1
```

Terminal 2:

```powershell
.\scripts\03_test_local_llm.ps1
.\scripts\04_check_llama_network.ps1
.\scripts\run_10.ps1
```

Escala:

```powershell
.\scripts\run_100.ps1
.\scripts\run_500.ps1
.\scripts\run_1000.ps1
```

Qualquer N:

```powershell
.\scripts\run_sample.ps1 -N 250
```

Processamento integral read-only:

```powershell
.\scripts\run_full_readonly.ps1
```

Retomar:

```powershell
.\scripts\resume_full_readonly.ps1
```

Leia `docs/GUIA_EXECUCAO_PGFN_WINDOWS.md`.
