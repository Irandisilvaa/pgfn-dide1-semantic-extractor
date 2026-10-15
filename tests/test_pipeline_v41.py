from pathlib import Path
from openpyxl import Workbook

from dide1.pipeline import executar
from dide1.teacher import ResultadoModelo


def _criar_xlsx(path: Path):
    wb = Workbook()
    ws = wb.active
    ws.append(["Processo", "Classe", "Origem", "Órgão Julgador", "Expediente", "Assunto", "Seção/Subseção", "Decisão Judicial", "Núcleo"])
    decisao = "DESPACHO\n\nIntime-se a parte para manifestação no prazo de 10 dias."
    ws.append(["P1", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (1)", "Tema", "AL / Maceió", decisao, "NTDC"])
    ws.append(["P1", "CumSenFaz", "PJE-AL", "1ª Vara Federal AL", "Intimação (2)", "Tema", "AL / Maceió", decisao, "NTDC"])
    wb.save(path)


def test_pipeline_reutiliza_cache_decisoes_identicas(tmp_path, monkeypatch):
    entrada = tmp_path / "in.xlsx"
    saida = tmp_path / "out"
    _criar_xlsx(entrada)
    chamadas = {"n": 0}

    def chamada_falsa(registro, unidades, roteamento, regra_encontrada, maximo_candidatos=3):
        chamadas["n"] += 1
        acionavel = [u for u in unidades if "Intime-se" in u.texto][0]
        return ResultadoModelo(
            selecionados=[{"unit_ids": [acionavel.id_unidade], "category": "intimacao_manifestacao", "priority": 1, "reason": "ok"}],
            situacao="OK",
            tentativas=1,
            modo_resposta="json_schema",
        )

    monkeypatch.setattr("dide1.pipeline.chamar_modelo", chamada_falsa)
    manifesto = executar(str(entrada), str(saida), limite=2, modo_modelo="llama")
    assert manifesto["processed"] == 2
    assert manifesto["errors"] == 0
    assert manifesto["unique_inferences"] == 1
    assert manifesto["cache_hits"] == 1
    assert chamadas["n"] == 1
