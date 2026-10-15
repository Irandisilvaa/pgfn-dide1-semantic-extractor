from dide1.router import familia_classe

def test_mandado_seguranca():
    assert familia_classe("Mandado de Segurança Cível") == "mandado_seguranca"

def test_cumprimento():
    assert familia_classe("Cumprimento de Sentença") == "cumprimento_sentenca"
