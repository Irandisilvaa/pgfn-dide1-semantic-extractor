# DIDE1 v4.1 — Teacher Resiliente

Correções motivadas pelo piloto real de 20 registros da base consolidada.

## Corrigido

1. Respostas do teacher em lista (`[...]`) agora são aceitas, além de `{"selected": [...]}`.
2. O cliente solicita JSON Schema quando o build do llama-server suporta e recua de forma compatível quando não suporta.
3. Resposta inválida é tentada novamente antes do fallback.
4. Falha do teacher pode ser recuperada por regra determinística, registrada como `RULE_FALLBACK`.
5. Assinaturas, timestamps, URLs/IDs e fechos genéricos não são enviados como unidades elegíveis ao teacher.
6. Ordens acionáveis terminadas em `:` não são descartadas e podem ser anexadas a listas a/b/c selecionadas.
7. Decisões exatamente idênticas usam cache SHA-256 durante a execução. Isso reduz custo e impede divergência aleatória em duplicatas.
8. Categorias de `tutela` incompatíveis com o conteúdo de perícia/habilitação são normalizadas para `ordem_determinacao`.

## teacher_status

- `OK`: primeira resposta válida com seleção.
- `RETRY_OK`: resposta válida após retry.
- `EMPTY_VALID`: resposta válida sem recorte.
- `RULE_FALLBACK`: teacher falhou e regra determinística recuperou o documento.
- `ERROR`: falha fatal, sem recuperação.

`cache_hit` é auditado separadamente para não alterar a semântica de `teacher_status`.
