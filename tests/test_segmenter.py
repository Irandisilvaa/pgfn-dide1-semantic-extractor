from dide1.segmenter import segment, reconstruct_exact

def test_reconstruct_exact():
    t = "RELATÓRIO\n\nNada.\n\nDISPOSITIVO\n\nIntime-se a União.\n\nApós, arquivem-se."
    u = segment(t)
    ids = [x.unit_id for x in u if "Intime-se" in x.text]
    assert reconstruct_exact(t, ids, u) == "Intime-se a União."
