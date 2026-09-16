
import json
from pathlib import Path


def rows(path):
    return [
        json.loads(x)
        for x in Path(path).read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]


def test_sizes():
    assert len(rows("data/benchmark_10.jsonl")) == 10
    assert len(rows("data/benchmark_100.jsonl")) == 100


def test_gold_is_literal_and_synthetic():
    for row in rows("data/benchmark_100.jsonl"):
        assert row["synthetic_only"] is True
        assert "DECISÃO SINTÉTICA PARA BENCHMARK" in row["decisao"]
        for gold in row["gold"]:
            assert gold["text"] in row["decisao"]
