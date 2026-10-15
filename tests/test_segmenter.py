from dide1.segmenter import segmentar, reconstruir_texto_exato

def test_reconstrucao_exata():
    t = "RELATÓRIO\n\nNada.\n\nDISPOSITIVO\n\nIntime-se a União.\n\nApós, arquivem-se."
    u = segmentar(t)
    ids = [x.id_unidade for x in u if "Intime-se" in x.texto]
    assert reconstruir_texto_exato(t, ids, u) == "Intime-se a União."
