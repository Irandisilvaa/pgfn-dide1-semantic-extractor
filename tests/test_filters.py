from dide1.filters import rejection_reason

def test_party_request():
    assert rejection_reason("No mérito, requer a total procedência da ação") == "likely_party_request"

def test_numeric():
    assert rejection_reason("25111006294315100000147581491") == "numeric_identifier_only"

def test_orphan_deadline():
    assert rejection_reason("Prazo para impugnação: 05 (cinco) dias.") == "orphan_deadline"
