from dide1.teacher import _ler_json, _extrair_selecoes, _expandir_unidades_pai
from dide1.segmenter import segmentar


def test_modelo_aceita_lista_no_nivel_principal():
    dados = _ler_json('[{"unit_ids":["U0001"],"category":"ordem_determinacao","priority":1,"reason":"ok"}]')
    selecionados, observacao = _extrair_selecoes(dados)
    assert len(selecionados) == 1
    assert observacao == "top_level_list"


def test_modelo_aceita_objeto_selected():
    dados = _ler_json('{"selected":[{"unit_ids":["U0001"],"category":"ordem_determinacao","priority":1,"reason":"ok"}]}')
    selecionados, observacao = _extrair_selecoes(dados)
    assert len(selecionados) == 1
    assert observacao == "selected_object"


def test_modelo_le_json_com_bloco_markdown():
    dados = _ler_json('```json\n{"selected": []}\n```')
    assert dados == {"selected": []}


def test_ordem_principal_e_adicionada_a_lista():
    texto = "DETERMINO que a contadoria faça os cálculos, devendo considerar:\n\na) o período correto;\nb) os índices legais."
    unidades = segmentar(texto)
    assert len(unidades) == 2
    ids = _expandir_unidades_pai([unidades[1].id_unidade], unidades)
    assert ids == [unidades[0].id_unidade, unidades[1].id_unidade]


def test_extracao_ignora_itens_que_nao_sao_objetos():
    selecionados, _ = _extrair_selecoes([{"unit_ids": ["U0001"]}, "junk", 3])
    assert selecionados == [{"unit_ids": ["U0001"]}]
