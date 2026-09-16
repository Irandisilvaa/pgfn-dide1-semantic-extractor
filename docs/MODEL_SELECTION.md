# Seleção do modelo — evidência e decisão de engenharia

## Escolha principal do piloto: Qwen3.5-9B

A escolha não significa que a literatura prove que ele é “o melhor modelo”
para a tarefa específica da PGFN. Não há benchmark público equivalente ao
nosso problema de recortes acionáveis de decisões PGFN.

Ele foi escolhido como candidato principal por:
- ser um modelo pós-treinado de 9B parâmetros;
- licença Apache 2.0;
- forte cobertura multilíngue;
- contexto longo;
- boa relação capacidade/memória em Q4;
- caber com folga operacional em uma RTX 3060 de 12 GB.

Fonte oficial:
https://huggingface.co/Qwen/Qwen3.5-9B

Quantização usada no benchmark:
https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF

## Candidato jurídico brasileiro: Jurema-7B

Jurema-7B é um fine-tune de Qwen2.5-7B-Instruct especializado no domínio
jurídico brasileiro. No benchmark OAB informado pelos autores, sobe de
0,5326 (Qwen2.5-7B-Instruct) para 0,6679; em OAB 2023, de 0,5765 para 0,6840.

Isso é evidência favorável à especialização jurídica, mas NÃO demonstra
superioridade na nossa tarefa extrativa. Além disso, o acesso ao checkpoint
é gated.

Fonte:
https://huggingface.co/Jurema-br/Jurema-7B

## Evidência brasileira diretamente ligada a Information Extraction

Dornelles (PROPOR 2026) usa Q-LoRA + geração JSON schema-constrained para
extrair 47 variáveis de decisões criminais brasileiras. O Phi-4 14B
fine-tunado alcançou 92,8% de accuracy e 0,826 macro-F1.

A principal implicação para DIDE1 não é “usar Phi-4 puro”, mas:
1. iniciar com um modelo local forte;
2. usar saída estruturada/constrangida;
3. coletar validação humana;
4. depois fazer ajuste de domínio com os dados rotulados.

Paper:
https://aclanthology.org/2026.propor-1.103/

## Por que não multiagente agora

Batitucci et al. (PROPOR 2026) avaliaram extração de metadados jurídicos
brasileiros com orquestração multiagente. O ganho dependeu da estratégia,
houve problemas de conclusão e maior complexidade/custo; modelos menores
Gemma 3 não mostraram ganho robusto com a orquestração.

Por isso o v2 usa uma arquitetura curta:
seleção por chunk -> adjudicação final.

Paper:
https://aclanthology.org/2026.propor-1.72/

## JSON Schema

O servidor llama.cpp suporta `response_format` com JSON/schema constrained
output. O v2 usa essa capacidade para restringir a geração a IDs/categorias
válidos.

Fonte:
https://github.com/ggml-org/llama.cpp/tree/master/tools/server
