
from src.semantic.segmenter import make_units


def test_e_trf_soft_line_merge():
    text = (
        "Considerando que, nos termos do Acórdão proferido no E.\n"
        "TRF da 5ª Região, foi negado provimento à Remessa Necessária."
    )

    units = make_units(text)
    assert len(units) == 1
    assert "E. TRF da 5ª Região" in units[0].text


def test_sections():
    text = (
        "RELATÓRIO\n"
        "A parte requereu restituição.\n"
        "FUNDAMENTAÇÃO\n"
        "A matéria foi analisada.\n"
        "DISPOSITIVO\n"
        "Diante do exposto, JULGO PROCEDENTE o pedido."
    )

    units = make_units(text)
    mapping = {
        u.text: u.section
        for u in units
    }

    assert mapping[
        "A parte requereu restituição."
    ] == "RELATORIO"

    assert mapping[
        "Diante do exposto, JULGO PROCEDENTE o pedido."
    ] == "DISPOSITIVO"
