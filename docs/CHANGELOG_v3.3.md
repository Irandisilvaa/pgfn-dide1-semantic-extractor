# DIDE1 v3.3.0 — hard-negative guards

Versão construída a partir do segundo piloto real (100 decisões inéditas processadas pela v3.2).

## Correções

- bloqueia identificadores puramente numéricos longos, que não são recortes jurídicos;
- amplia a detecção de histórico processual, inclusive construções como `Por meio de despacho datado de... este Juízo determinou...`;
- bloqueia citações de julgados externos quando a unidade contém metadados fortes de outro processo (`PROCESSO`, relator/turma e `JULGAMENTO`);
- amplia a detecção de pedidos da parte, inclusive itens `(ii) ao final, o reconhecimento...` e verbos no infinitivo como `Determinar...`;
- bloqueia prazos órfãos do tipo `Prazo para impugnação: 05 dias`;
- bloqueia cabeçalhos incompletos terminados em dois-pontos, mesmo quando contêm verbo dispositivo (`DETERMINO, com urgência:`);
- melhora dicas determinísticas de categoria para `cite-se`, `retifique-se`, `encaminhe-se`, `proceda-se`, `expeça-se` e comandos semelhantes;
- adiciona exportação local para auditoria humana de documentos que ficaram com `candidate_rank=0`.

## Segurança

Nenhum dado real deve ser versionado. `data_private/`, `runtime/` e planilhas são ignorados pelo Git.

## Testes

A release contém 37 testes automatizados, incluindo regressões baseadas nos padrões observados no piloto real v3.2.
