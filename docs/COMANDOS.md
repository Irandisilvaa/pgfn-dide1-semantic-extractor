# Comandos de execução

## 1) PC pessoal — 20 decisões
Use apenas amostra sanitizada ou cuja cópia no equipamento pessoal tenha autorização institucional. Não copie a base real da PGFN para notebook pessoal apenas para testar.

```bash
cd pgfn-dide1-router-v4
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pytest -q
```

Coloque a amostra em `dados/amostra_20.xlsx` e valide:
```bash
python -m dide1.cli inspect --input dados/amostra_20.xlsx
```

Smoke test da arquitetura, sem LLM:
```bash
python -m dide1.cli run --input dados/amostra_20.xlsx --limit 20 --teacher rules --output runtime/piloto20_local
```

Se houver um `llama-server` local com Qwen disponível, troque `--teacher rules` por `--teacher llama`.

## 2) Máquina PGFN — preparação
```powershell
cd C:\PGFN\DIDE1\pgfn-dide1-router-v4
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
```

Coloque a planilha real somente no checkout local:
`dados\base_consolidada.xlsx`

Confirme que o Git ignora a planilha:
```powershell
git check-ignore -v dados\base_consolidada.xlsx
```

Inspecione a base:
```powershell
.\.venv\Scripts\python.exe -m dide1.cli inspect --input dados\base_consolidada.xlsx
```

## 3) Subir Qwen3.5-9B localmente na GPU PGFN
Em um terminal separado:
```powershell
C:\PGFN\DIDE1\llama\llama-server.exe -m C:\PGFN\DIDE1\models\Qwen3.5-9B-Q4_K_M.gguf -c 8192 -t 8 -np 1 -ngl 999 --host 127.0.0.1 --port 8081 --no-webui --reasoning off
```

Teste:
```powershell
Invoke-RestMethod http://127.0.0.1:8081/health
```

## 4) Progressão validada
A ideia é não pular diretamente para 10.000.

### Próximas 100 após o piloto de 20
```powershell
.\.venv\Scripts\python.exe -m dide1.cli run --input dados\base_consolidada.xlsx --start-index 20 --limit 100 --teacher llama --output runtime\lote_0021_0120
```

Revise `runtime\lote_0021_0120\review.xlsx` antes de avançar.

### Próximas 1.000
```powershell
.\.venv\Scripts\python.exe -m dide1.cli run --input dados\base_consolidada.xlsx --start-index 120 --limit 1000 --teacher llama --output runtime\lote_0121_1120
```

### Restante até completar 10.000
```powershell
.\.venv\Scripts\python.exe -m dide1.cli run --input dados\base_consolidada.xlsx --start-index 1120 --limit 8880 --teacher llama --output runtime\lote_1121_10000
```

## 5) Criar GOLD após revisão
Exemplo:
```powershell
.\.venv\Scripts\python.exe -m dide1.cli build-gold --review runtime\lote_0021_0120\review.xlsx --output runtime\gold\gold_lote100.jsonl
```

Depois, consulte `docs/TREINAMENTO.md`.
