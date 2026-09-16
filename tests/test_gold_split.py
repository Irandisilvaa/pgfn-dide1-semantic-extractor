from src.annotation.build_gold import split_process_groups


def test_process_never_crosses_splits():
    records = [
        {"source_row": 1, "Processo": "A"},
        {"source_row": 2, "Processo": "A"},
        {"source_row": 3, "Processo": "B"},
        {"source_row": 4, "Processo": "C"},
        {"source_row": 5, "Processo": "D"},
        {"source_row": 6, "Processo": "E"},
    ]
    assignment = split_process_groups(records, 42, 0.6, 0.2)
    assert set(assignment) == {"A", "B", "C", "D", "E"}
    assert assignment["A"] in {"train", "val", "test"}
