from dide1.filters import motivo_rejeicao

def test_pedido_da_parte():
    assert motivo_rejeicao("No mérito, requer a total procedência da ação") == "likely_party_request"

def test_identificador_numerico():
    assert motivo_rejeicao("25111006294315100000147581491") == "numeric_identifier_only"

def test_prazo_sem_contexto():
    assert motivo_rejeicao("Prazo para impugnação: 05 (cinco) dias.") == "orphan_deadline"
