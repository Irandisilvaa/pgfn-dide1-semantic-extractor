from dide1.filters import rejection_reason


def test_signature_block_rejected():
    assert rejection_reason("Assinado eletronicamente por FULANO DE TAL\n20/01/2026 13:10:46") == "signature_or_timestamp"


def test_generic_closing_rejected():
    assert rejection_reason("Intimações e providências necessárias.") == "generic_closing_fragment"


def test_actionable_parent_with_colon_is_kept():
    assert rejection_reason("DETERMINO que a contadoria faça os cálculos, devendo considerar:") is None


def test_location_date_boilerplate_rejected():
    assert rejection_reason("Arapiraca-AL, data e hora registradas no sistema.") == "location_date_boilerplate"
