
from src.semantic.deterministic_filters import (
    infer_category_hint,
    low_value_reason,
)


def test_noise_filters():
    assert low_value_reason("06/02/2026 10:29:43") == "date_only"
    assert low_value_reason("12ª Vara Federal PE") == "court_header"
    assert low_value_reason("Cumpra-se.") == "generic_command"
    assert low_value_reason("Intime(m)-se.") == "generic_command"
    assert low_value_reason("Decorrido o prazo:") == "preparatory_fragment"
    assert low_value_reason(
        "Nos termos do art. 203, passo a realizar o seguinte ato ordinatório:"
    ) == "preparatory_fragment"


def test_actionable_kept():
    text = (
        "Intime-se a Fazenda Nacional para apresentar impugnação "
        "no prazo de 30 dias."
    )
    assert low_value_reason(text) is None


def test_category_hints():
    assert infer_category_hint(
        "Sem condenação em honorários advocatícios."
    ) == "honorarios_custas"

    assert infer_category_hint(
        "Condeno a União a restituir os valores."
    ) == "restituicao_pagamento"
