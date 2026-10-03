# DIDE1 v4 — decisões de engenharia

## Decisões trazidas da reunião

1. Escopo inicial: defesa cível. Execução fiscal fica fora por já possuir fluxo próprio.
2. Prioridade: acurácia de classificação/extração antes de automação de peticionamento.
3. Reaproveitar conhecimento existente: regras textuais/fórmulas já usadas pela equipe viram baseline determinístico.
4. Usar metadados processuais como contexto de roteamento: Classe, Órgão Julgador, Expediente, Assunto, Seção/Subseção e Núcleo.
5. Medir diferenças por classe/região/vara antes de criar um modelo dedicado para cada vara.
6. Teacher local Qwen gera pré-anotação; procuradores fazem revisão da decisão inteira; somente então nasce GOLD.
7. QLoRA entra depois do GOLD para especializar um SLM menor.
8. Todo processamento de decisões reais deve permanecer em infraestrutura autorizada da PGFN.

## Colunas descartadas nesta fase

`tag_decisão`, `Integra_2x`, `Incluir na triagem?`, `Classificação NTDC` e `Classificação NDE` não participam desta versão.

## Arquitetura

Planilha local -> filtro de escopo -> RuleEngine Jovaldo -> normalização -> Router -> Qwen Teacher -> reconstrução exata -> workbook de revisão -> GOLD -> QLoRA/SLM.

## Por que Router + especialistas, e não um modelo completo por vara?

Um modelo completo por vara multiplica custo, VRAM, armazenamento e manutenção. A v4 registra `route_key` (classe + região + órgão) e começa com um teacher global. Depois do GOLD, mede-se F1/recall por grupo. Somente grupos com volume suficiente e ganho comprovado recebem adapters QLoRA específicos. O fallback permanece global.

## Regra de ouro contra leakage

Rótulos ou classificações humanas existentes nunca devem entrar como feature quando forem o alvo a ser previsto.
