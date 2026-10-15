import argparse
import json

from .pipeline import executar
from .inspect_data import inspecionar_dados
from .workbook import construir_gold, reconstruir_revisao


def principal():
    analisador = argparse.ArgumentParser(prog="dide1")
    subcomandos = analisador.add_subparsers(dest="comando", required=True)

    comando_inspecionar = subcomandos.add_parser("inspect", help="Valida e resume a planilha")
    comando_inspecionar.add_argument("--input", dest="entrada", required=True)
    comando_inspecionar.add_argument("--sheet", dest="aba")
    comando_inspecionar.add_argument("--limit", dest="limite", type=int)

    comando_executar = subcomandos.add_parser("run", help="Executa pipeline de extração/teacher")
    comando_executar.add_argument("--input", dest="entrada", required=True)
    comando_executar.add_argument("--output", dest="saida", required=True)
    comando_executar.add_argument("--sheet", dest="aba")
    comando_executar.add_argument("--limit", dest="limite", type=int, help="Limite de linhas/expedientes escaneados")
    comando_executar.add_argument("--unique-limit", dest="limite_unicos", type=int, help="Limite de decisões únicas por SHA-256; ideal para lotes de revisão")
    comando_executar.add_argument("--start-index", dest="indice_inicial", type=int, default=0)
    comando_executar.add_argument("--teacher", dest="modo_modelo", choices=["llama", "rules"], default="llama")
    comando_executar.add_argument("--max-candidates", dest="maximo_candidatos", type=int, default=3)
    comando_executar.add_argument("--include-execucao-fiscal", dest="incluir_execucao_fiscal", action="store_true")

    comando_reconstruir = subcomandos.add_parser("rebuild-review", help="Recria somente o review.xlsx em layout compacto, sem chamar o Qwen")
    comando_reconstruir.add_argument("--review", dest="revisao", required=True, help="review.xlsx existente da v4.2/v4.3")
    comando_reconstruir.add_argument("--output", dest="saida", required=True, help="novo .xlsx compacto")

    comando_gold = subcomandos.add_parser("build-gold", help="Converte workbook humano revisado em GOLD JSONL")
    comando_gold.add_argument("--review", dest="revisao", required=True)
    comando_gold.add_argument("--output", dest="saida", required=True)

    argumentos = analisador.parse_args()

    if argumentos.comando == "inspect":
        resultado = inspecionar_dados(argumentos.entrada, argumentos.aba, argumentos.limite)
    elif argumentos.comando == "run":
        resultado = executar(
            argumentos.entrada,
            argumentos.saida,
            argumentos.limite,
            argumentos.indice_inicial,
            argumentos.aba,
            argumentos.modo_modelo,
            argumentos.maximo_candidatos,
            argumentos.incluir_execucao_fiscal,
            argumentos.limite_unicos,
        )
    elif argumentos.comando == "rebuild-review":
        resultado = reconstruir_revisao(argumentos.revisao, argumentos.saida)
    else:
        resultado = construir_gold(argumentos.revisao, argumentos.saida)

    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    principal()
