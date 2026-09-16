
from src.semantic.action_extractor import ActionOrientedExtractor


def test_chunk_schema_enumerates_ids():
    s = ActionOrientedExtractor._chunk_schema(["P0001", "P0002"], 3)
    enum = s["properties"]["recortes"]["items"]["properties"]["id"]["enum"]
    assert enum == ["P0001", "P0002"]


def test_final_schema_enumerates_candidates():
    s = ActionOrientedExtractor._final_schema(["C01", "C02"], 1)
    assert s["properties"]["selecionados"]["items"]["enum"] == ["C01", "C02"]
    assert s["properties"]["selecionados"]["maxItems"] == 1
