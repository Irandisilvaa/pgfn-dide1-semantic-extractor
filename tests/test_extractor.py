
from src.semantic.action_extractor import ActionOrientedExtractor


class FakeClient:
    def chat_json(
        self,
        *,
        system,
        user,
        temperature,
        max_tokens,
    ):
        if "UNIDADES:" in user:
            return {
                "recortes": [
                    {
                        "id": "P0004",
                        "categoria": "ordem_determinacao",
                        "prioridade": 5,
                    }
                ]
            }

        if "CANDIDATOS:" in user and "MANter=true" in user:
            return {
                "avaliacoes": [
                    {
                        "candidate": "C01",
                        "manter": True,
                        "relevancia": 5,
                    }
                ]
            }

        return {
            "selecionados": ["C01"]
        }


def test_extraction_is_literal():
    decision = (
        "RELATÓRIO\n"
        "A parte apresentou pedido.\n"
        "DISPOSITIVO\n"
        "Intime-se a Fazenda Nacional para apresentar impugnação "
        "no prazo de 30 dias."
    )

    extractor = ActionOrientedExtractor(
        FakeClient(),
        max_chunk_chars=3000,
        max_unit_chars=1000,
        temperature=0,
    )

    result = extractor.extract(
        decision,
        top_k=3,
    )

    assert len(result["recortes"]) == 1
    rec = result["recortes"][0]

    assert rec["text"] == (
        "Intime-se a Fazenda Nacional para apresentar impugnação "
        "no prazo de 30 dias."
    )
    assert rec["validator_status"] == "PASSED"
    assert rec["unit_ids"] == ["P0004"]


class BatchFailClient:
    def chat_json(
        self,
        *,
        system,
        user,
        temperature,
        max_tokens,
    ):
        if "UNIDADES:" in user:
            return {
                "recortes": [
                    {
                        "id": "P0001",
                        "categoria": "ordem_determinacao",
                        "prioridade": 5,
                    }
                ]
            }

        if "MANter=true" in user:
            raise RuntimeError("simulated validator failure")

        return {"selecionados": ["C01"]}


def test_validator_error_is_visible():
    decision = (
        "Intime-se a Fazenda Nacional para apresentar impugnação "
        "no prazo de 30 dias."
    )

    extractor = ActionOrientedExtractor(
        BatchFailClient(),
        validator_batch_size=6,
    )

    result = extractor.extract(
        decision,
        top_k=1,
    )

    assert result["validator_failed"] == 1
    assert result["recortes"][0]["validator_status"] == "ERROR"
