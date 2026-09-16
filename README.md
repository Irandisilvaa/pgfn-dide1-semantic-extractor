# PGFN DIDE1 — Teacher → GOLD → SLM v3.2.0

Pipeline local para ler uma planilha XLSX real, gerar candidatos com o Qwen3.5-9B local, obter validação humana e depois treinar um Small Language Model especializado.

## Arquitetura

```text
XLSX real PGFN LOCAL
        ↓
Qwen3.5-9B local = TEACHER
        ↓
XLSX de revisão humana
        ↓
procurador aprova / rejeita / ajusta / adiciona recorte
        ↓
DIDE1-GOLD
        ↓
split por Processo
        ↓
SFT / QLoRA do SLM
        ↓
DIDE1-SLM
        ↓
checkpoints + adapter_final + modelo mesclado opcional
```

## Mudanças da v3.2

A v3.2 mantém a entrada XLSX local da v3.1 e incorpora correções derivadas do primeiro piloto real de 100 decisões, sem versionar qualquer decisão real:

- filtro conservador para itens que parecem **pedido da parte**, como enumerações em modo subjuntivo/imperativo;
- filtro para referências claras a **decisões anteriores** (`decisão/sentença de id...`);
- rejeição de fragmentos órfãos, como prazo isolado e comando genérico sem conteúdo;
- melhor precedência de categorias para resultado do julgamento, tutela e próximo passo recursal;
- promoção de decisum textual claro para seção `DISPOSITIVO`;
- prompt final reforçado: score heurístico nunca substitui a distinção pedido x decisão x histórico;
- script `14_teacher_export_next_100_v32.ps1` para testar **100 decisões novas**, retomando automaticamente da próxima linha do checkpoint anterior quando disponível;
- script `15_teacher_export_next_500_v32.ps1` preparado para a etapa seguinte, mas só deve ser usado após revisão do novo lote de 100.

## Mudança da v3.1

Não existe dependência de API de planilha, token ou `SPREADSHEET_ID`.

A entrada é um arquivo `.xlsx` colocado **localmente na máquina institucional**, por padrão:

```text
data_private/entrada_pgfn.xlsx
```

A aba padrão é `input` e deve ter os cabeçalhos:

```text
Extração | Processo | Classe judicial | Órgão julgador | Polo Ativo |
Polo Passivo | Decisão | Matéria SAJ | Ind. | tags
```

`Processo` e `Decisão` são obrigatórios. As demais colunas são preservadas quando presentes.

## Segurança dos dados reais

- o Qwen aceita apenas `127.0.0.1/localhost`;
- não existe API externa de LLM;
- não existe API de planilha nesta versão;
- `tags` e `Ind.` são preservados para revisão, mas não entram no prompt do teacher;
- a planilha fonte é aberta em read-only e nunca é alterada;
- `data_private/`, `runtime/`, planilhas reais, GOLD e modelos são ignorados pelo Git;
- **não faça commit/push da planilha real para o GitHub**;
- GitHub deve transportar apenas o código e os benchmarks sintéticos.

## 1. Preparar o repositório na máquina PGFN

Depois de clonar o código, coloque a planilha real localmente em:

```text
data_private/entrada_pgfn.xlsx
```

Se o nome for diferente, passe `-InputXlsx` nos scripts.

## 2. Instalar dependências Python

```powershell
.\scripts\01_setup_python.ps1
```

## 3. Validar a planilha antes de usar o LLM

```powershell
.\scripts\09_validate_input_xlsx.ps1
```

Ou, com outro nome/aba:

```powershell
.\scripts\09_validate_input_xlsx.ps1 -InputXlsx "C:\CAMINHO\arquivo.xlsx" -Sheet "input"
```

O validador mostra quantidade de linhas, decisões vazias, processos únicos e cabeçalhos reconhecidos. Ele não imprime o conteúdo das decisões.

## 4. Iniciar o Qwen local

```powershell
.\scripts\02_start_llama_local.ps1
```

Padrões já configurados:

```text
llama.cpp: C:\PGFN\DIDE1\llama\llama-server.exe
modelo:    C:\PGFN\DIDE1\models\Qwen3.5-9B-Q4_K_M.gguf
host:      127.0.0.1
porta:     8081
```

Não é necessário `.env`.

## 5. Gerar 20 anotações primeiro

Em outro PowerShell:

```powershell
.\scripts\10_teacher_export_20.ps1
```

Saída:

```text
runtime/private_annotations/teacher_review_20.xlsx
```

Depois faça 100:

```powershell
.\scripts\11_teacher_export_100.ps1
```

Na v3.2, para avaliar as correções em **100 decisões novas** sem repetir as primeiras 100 linhas de dados:

```powershell
.\scripts\14_teacher_export_next_100_v32.ps1
```

Por padrão, esse script lê `teacher_100_checkpoint.json` e começa na próxima linha ainda não processada. Se o checkpoint não existir, usa a linha Excel `102`. Ele gera:

```text
runtime/private_annotations/teacher_review_v32_next100.xlsx
```

Só depois da revisão desse lote, o próximo lote preparado é:

```powershell
.\scripts\15_teacher_export_next_500_v32.ps1
```

E somente depois rode a planilha inteira:

```powershell
.\scripts\12_teacher_export_full.ps1
```

Se interromper:

```powershell
.\scripts\13_teacher_resume_full.ps1
```

O checkpoint registra a próxima linha do Excel e impede retomar acidentalmente com outra planilha/aba.

## 6. Revisão humana

A saída contém:

- `decisoes`: decisão integral + status do documento;
- `candidatos`: 1–3 candidatos do teacher;
- `adicoes_gold`: recortes que o teacher deixou escapar;
- `instrucoes`: protocolo de revisão;
- `manifesto`: versão, modelo e origem local.

Candidato:

```text
APROVADO | AJUSTADO | REJEITADO | SEM_RECORTE
```

Documento:

```text
VALIDADO_COMPLETO | SEM_RECORTE | PRECISA_REVISAO
```

A saída do teacher **não é GOLD** até a validação humana.

## 7. Construir GOLD e dataset SFT

```powershell
.\scripts\20_build_gold.ps1 -ReviewXlsx runtime\private_annotations\teacher_review_100.xlsx
```

Gera em `runtime/private_gold/`:

```text
gold_records.jsonl
sft_train.jsonl
sft_val.jsonl
sft_test.jsonl
gold_build_issues.csv
manifest.json
```

O split é por `Processo`, nunca por linha.

## 8. Treinar o SLM com QLoRA

Exemplo:

```powershell
.\scripts\30_train_qlora.ps1 -BaseModel "Qwen/Qwen3-4B" -RunName "dide1-slm-v1"
```

Retomar após interrupção:

```powershell
.\scripts\31_resume_qlora.ps1 -BaseModel "Qwen/Qwen3-4B" -RunName "dide1-slm-v1"
```

## 9. Persistência do modelo

Cada treino salva:

```text
artifacts/models/dide1-slm-v1/
├── checkpoints/
├── adapter_final/
├── metrics.json
├── training_manifest.json
└── SHA256SUMS.json
```

Para gerar um modelo mesclado independente do adapter:

```powershell
.\scripts\32_merge_adapter.ps1 -BaseModel "Qwen/Qwen3-4B" -RunName "dide1-slm-v1"
```

Para backup em armazenamento institucional aprovado:

```powershell
.\scripts\33_backup_model.ps1 -RunName "dide1-slm-v1" -Destination "D:\CAMINHO_APROVADO"
```

Modelos, adapters, planilhas reais e datasets reais não devem ser enviados ao GitHub.

## Benchmark sintético

Os 100 casos sintéticos permanecem em `data/benchmark_100.jsonl` para regressão do pipeline. Dados sintéticos podem ser versionados; dados reais não.

---

## v3.3.0 — hard-negative guards

A v3.3 incorpora regressões encontradas no segundo piloto real. Ela bloqueia IDs numéricos puros, referências históricas, citações externas de outros julgados, pedidos da parte em formatos adicionais, prazos órfãos e cabeçalhos incompletos. Também inclui uma ferramenta local para auditar decisões que ficaram sem candidato antes de reduzir recall por excesso de filtragem.

Fluxo recomendado: `100 v3.2 -> auditoria dos zeros -> 100 inéditas v3.3 -> revisão -> 500`.
