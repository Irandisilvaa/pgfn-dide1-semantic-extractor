from dide1.router import class_family

def test_ms():
    assert class_family("Mandado de Segurança Cível") == "mandado_seguranca"

def test_cumprimento():
    assert class_family("Cumprimento de Sentença") == "cumprimento_sentenca"
