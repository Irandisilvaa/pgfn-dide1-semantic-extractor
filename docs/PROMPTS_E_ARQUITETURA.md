# Prompts e arquitetura

Os três prompts estão em:

```text
src/semantic/action_extractor.py
```

- `SYSTEM_PROMPT`
- `CHUNK_PROMPT`
- `VALIDATOR_PROMPT`
- `FINAL_PROMPT`

## Correções consolidadas

A v1.0 incorpora os problemas observados nos pilotos:

- bloqueio de cabeçalho e data isolada;
- bloqueio de `Cumpra-se.` / `Intime(m)-se.` sozinhos;
- bloqueio de `12ª Vara Federal ...`;
- bloqueio de frases preparatórias como `Decorrido o prazo:`;
- tratamento de `E. TRF` como abreviação;
- um ID por seleção inicial;
- contexto adjacente só por regra controlada;
- validador em lotes pequenos;
- lote inválido é dividido recursivamente;
- falha individual aparece como `validator_status=ERROR`;
- ranking favorece conteúdo acionável do `DISPOSITIVO`;
- categoria pode ser corrigida por regras fortes de texto.
