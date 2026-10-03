from dide1.teacher import _parse_json, _extract_selected, _expand_parent_units
from dide1.segmenter import segment


def test_teacher_accepts_top_level_list():
    data = _parse_json('[{"unit_ids":["U0001"],"category":"ordem_determinacao","priority":1,"reason":"ok"}]')
    selected, note = _extract_selected(data)
    assert len(selected) == 1
    assert note == "top_level_list"


def test_teacher_accepts_selected_object():
    data = _parse_json('{"selected":[{"unit_ids":["U0001"],"category":"ordem_determinacao","priority":1,"reason":"ok"}]}')
    selected, note = _extract_selected(data)
    assert len(selected) == 1
    assert note == "selected_object"


def test_teacher_parses_fenced_json():
    data = _parse_json('```json\n{"selected": []}\n```')
    assert data == {"selected": []}


def test_parent_order_is_added_to_list():
    text = "DETERMINO que a contadoria faça os cálculos, devendo considerar:\n\na) o período correto;\nb) os índices legais."
    units = segment(text)
    assert len(units) == 2
    ids = _expand_parent_units([units[1].unit_id], units)
    assert ids == [units[0].unit_id, units[1].unit_id]


def test_extract_selected_ignores_non_dict_items():
    selected, _ = _extract_selected([{"unit_ids": ["U0001"]}, "junk", 3])
    assert selected == [{"unit_ids": ["U0001"]}]
