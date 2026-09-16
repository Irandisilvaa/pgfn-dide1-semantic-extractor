# Protocolo do piloto

## Fase A — sintético

1. Rodar 10 documentos.
2. Verificar zero erro de JSON.
3. Verificar zero duplicata final.
4. Inspecionar manualmente cada PRED.
5. Rodar os 100 documentos.
6. Registrar Precision, Recall, F1, Hit@1 e wall time.

## Gate para avançar

Não existe limiar científico pré-definido para PGFN neste benchmark
sintético. Como gate interno inicial sugerido:

- zero erro estrutural/JSON;
- zero duplicata final;
- Precision exata >= 0,80;
- Recall exato >= 0,70;
- revisão manual dos casos difíceis.

Se não atingir, comparar modelo/prompt antes de dados reais.

## Fase B — real, institucional

Somente após autorização e na máquina institucional:

- amostra pequena;
- sem API externa;
- texto permanece local;
- revisão humana de cada recorte;
- nenhum overwrite de tags/indicadores existentes.

Os resultados reais devem ser reportados separadamente dos sintéticos.

## Gate v3.2 após o primeiro lote real

Antes de escalar o teacher para 500+ decisões, revisar um lote novo de 100 e registrar manualmente:

- falso positivo por **pedido da parte**;
- falso positivo por **referência histórica**;
- fragmento órfão / semanticamente incompleto;
- categoria incorreta;
- decisão sem candidato que possua recorte acionável (falso negativo);
- candidatos aprovados, ajustados e rejeitados.

O `heuristic_score` não é probabilidade de acerto e não deve ser usado como GOLD.
A anotação do teacher só vira GOLD após validação humana completa da decisão.
