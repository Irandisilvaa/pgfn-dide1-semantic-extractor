from dide1.rules_jovaldo import classify

def test_jovaldo_order_migration():
    m = classify("O presente processo foi migrado para este sistema eletrônico", "Sentença")
    assert m.rule_id == "J01"

def test_exp_sentence():
    m = classify("texto qualquer", "Sentença")
    assert m.label == "sentença"

def test_contrarrazones():
    m = classify("texto", "Intimação para Contrarrazões")
    assert m.label == "contrarrazões"
