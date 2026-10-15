from dide1.rules_jovaldo import classificar

def test_ordem_jovaldo_migracao():
    m = classificar("O presente processo foi migrado para este sistema eletrônico", "Sentença")
    assert m.id_regra == "J01"

def test_expediente_sentenca():
    m = classificar("texto qualquer", "Sentença")
    assert m.rotulo == "sentença"

def test_contrarrazoes():
    m = classificar("texto", "Intimação para Contrarrazões")
    assert m.rotulo == "contrarrazões"
