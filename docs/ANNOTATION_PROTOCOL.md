# Protocolo de anotação humana — DIDE1-GOLD

## Definição de recorte GOLD

Um recorte é GOLD quando:
1. é literal da decisão;
2. faz sentido isoladamente;
3. comunica consequência, ordem, resultado, prazo, obrigação, intimação, tutela ou providência processual relevante;
4. pode orientar reconhecimento de indicador/tag ou ação do procurador.

## Regra de completude

Revisar candidatos não basta. O revisor deve ler a decisão inteira e verificar se o teacher deixou escapar algum recorte. Recortes ausentes entram em `adicoes_gold`.

Só depois disso marque `status_documento=VALIDADO_COMPLETO`.

## O que NÃO deve ser GOLD

- narrativa de pedido/alegação;
- transcrição de lei ou jurisprudência sem consequência concreta;
- cabeçalho, data, assinatura;
- comando genérico isolado (`Cumpra-se`, `Intimem-se`) sem conteúdo suficiente;
- texto inventado ou reescrito.

## Ajustes

`AJUSTADO` deve usar texto literal da decisão. O builder exige que o texto final corresponda a uma única unidade semântica do segmentador. Se não corresponder, o documento vai para `gold_build_issues.csv`.
