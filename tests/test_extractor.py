
from src.semantic.action_extractor import ActionOrientedExtractor


class FakeClient:
    def __init__(self):
        self.n = 0

    def chat_json(self, *, system, user, schema, temperature, max_tokens):
        self.n += 1
        # Chunk: escolhe um recorte literal válido.
        if "recortes" in schema["properties"]:
            ids = schema["properties"]["recortes"]["items"]["properties"]["id"]["enum"]
            return {
                "recortes": [
                    {
                        "id": ids[-1],
                        "categoria": "intimacao_manifestacao",
                        "prioridade": 5,
                    }
                ]
            }
        # Final: mantém primeiro candidato.
        ids = schema["properties"]["selecionados"]["items"]["enum"]
        return {"selecionados": ids[:1]}


def test_pipeline_smoke():
    decision = """
PODER JUDICIÁRIO
RELATÓRIO
A parte autora alega cobrança tributária indevida e requer providências judiciais.
DISPOSITIVO
Intime-se a Fazenda Nacional para apresentar impugnação no prazo de 30 dias.
"""
    result = ActionOrientedExtractor(FakeClient()).extract(decision, top_k=1)
    assert len(result["recortes"]) == 1
    assert "Intime-se a Fazenda Nacional" in result["recortes"][0]["text"]
