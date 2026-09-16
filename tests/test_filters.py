
from src.semantic.deterministic_filters import low_value_reason, infer_category_hint


def test_narrative_request_filtered():
    t = "A parte autora alega cobrança tributária indevida e requer providências judiciais."
    assert low_value_reason(t) == "narrative_or_argument"


def test_generic_law_filtered():
    t = "A legislação de regência contém regras gerais sobre prazos, competência e formação da relação processual."
    assert low_value_reason(t) == "narrative_or_argument"


def test_dispositive_not_filtered():
    t = "Intime-se a Fazenda Nacional para apresentar impugnação no prazo de 30 dias."
    assert low_value_reason(t) is None


def test_julgo_procedente_is_result():
    t = "JULGO PROCEDENTE o pedido para reconhecer o direito à restituição."
    assert infer_category_hint(t) == "resultado_julgamento"
