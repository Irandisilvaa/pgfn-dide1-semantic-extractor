from dide1.filters import motivo_rejeicao


def test_bloco_assinatura_rejeitado():
    assert motivo_rejeicao("Assinado eletronicamente por FULANO DE TAL\n20/01/2026 13:10:46") == "signature_or_timestamp"


def test_fecho_generico_rejeitado():
    assert motivo_rejeicao("Intimações e providências necessárias.") == "generic_closing_fragment"


def test_ordem_principal_com_dois_pontos_e_mantida():
    assert motivo_rejeicao("DETERMINO que a contadoria faça os cálculos, devendo considerar:") is None


def test_local_data_padrao_rejeitado():
    assert motivo_rejeicao("Arapiraca-AL, data e hora registradas no sistema.") == "location_date_boilerplate"


def test_fecho_generico_numerado_rejeitado():
    assert motivo_rejeicao("9. Intimações e providências necessárias.") == "generic_closing_fragment"


def test_intimem_se_isolado_rejeitado():
    assert motivo_rejeicao("3. Intimem-se.") == "generic_closing_fragment"
