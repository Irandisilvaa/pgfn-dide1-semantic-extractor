from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from dide1.segmenter import segmentar
from dide1.constants import CATEGORIAS
from dide1.router import rotear

PROMPT_SISTEMA = """Você é o classificador especializado DIDE1/PGFN. Selecione somente IDs de unidades da decisão atual que formem recortes juridicamente acionáveis. Não invente texto. Retorne JSON puro no formato {\"selected\":[{\"unit_ids\":[\"U0001\"],\"category\":\"categoria\"}]}."""


def dividir_estavel(processo: str) -> str:
    h = int(hashlib.sha256(processo.encode("utf-8")).hexdigest()[:8], 16) % 100
    if h < 80: return "train"
    if h < 90: return "val"
    return "test"


def mapear_gold_para_unidades(decisao: str, itens_gold: list[dict]):
    unidades = segmentar(decisao)
    selecionados = []
    problemas = []
    for g in itens_gold:
        texto = str(g.get("text", ""))
        categoria = str(g.get("category", ""))
        if categoria not in CATEGORIAS:
            problemas.append({"reason": "invalid_category", "text": texto, "category": categoria})
            continue
        posicao = decisao.find(texto)
        if posicao < 0:
            problemas.append({"reason": "gold_not_exact_source", "text": texto, "category": categoria})
            continue
        fim = posicao + len(texto)
        ids = [u.id_unidade for u in unidades if not (u.fim <= posicao or u.inicio >= fim)]
        if not ids:
            problemas.append({"reason": "no_units_for_gold", "text": texto, "category": categoria})
            continue
        selecionados.append({"unit_ids": ids, "category": categoria})
    return unidades, selecionados, problemas


def construir_sft(arquivo_gold_jsonl: str, pasta_saida: str):
    saida = Path(pasta_saida); saida.mkdir(parents=True, exist_ok=True)
    arquivos_saida = {s: (saida / f"sft_{s}.jsonl").open("w", encoding="utf-8") for s in ("train","val","test")}
    arquivo_problemas = (saida / "sft_issues.jsonl").open("w", encoding="utf-8")
    contagens = {"train":0,"val":0,"test":0,"issues":0}
    with open(arquivo_gold_jsonl, encoding="utf-8") as f:
        for linha in f:
            if not linha.strip(): continue
            objeto = json.loads(linha)
            decisao = objeto.get("decision", "")
            processo = str(objeto.get("Processo") or objeto.get("source_row"))
            unidades, selecionados, problemas = mapear_gold_para_unidades(decisao, objeto.get("gold", []))
            for problema in problemas:
                arquivo_problemas.write(json.dumps({"Processo": processo, **problema}, ensure_ascii=False)+"\n")
                contagens["issues"] += 1
            if problemas:
                # Não treinar exemplo com GOLD não-extrativo: precisa correção humana primeiro.
                continue
            metadados = objeto.get("metadata", {})
            roteamento = rotear({
                "classe": metadados.get("classe", ""), "orgao_julgador": metadados.get("orgao_julgador", ""),
                "secao_subsecao": metadados.get("secao_subsecao", "")
            })
            unidades_visiveis = [u for u in unidades if not u.rejeitada]
            mensagem_usuario = {
                "contexto": {
                    "classe": metadados.get("classe", ""), "orgao_julgador": metadados.get("orgao_julgador", ""),
                    "expediente": metadados.get("expediente", ""), "assunto": metadados.get("assunto", ""),
                    "secao_subsecao": metadados.get("secao_subsecao", ""), "routing": roteamento,
                },
                "unidades": [{"id":u.id_unidade,"section":u.secao,"text":u.texto} for u in unidades_visiveis],
                "categorias_permitidas": CATEGORIAS,
            }
            resposta_assistente = {"selected": selecionados}
            registro_gold = {"messages":[
                {"role":"system","content":PROMPT_SISTEMA},
                {"role":"user","content":json.dumps(mensagem_usuario, ensure_ascii=False)},
                {"role":"assistant","content":json.dumps(resposta_assistente, ensure_ascii=False)},
            ], "Processo": processo}
            particao = dividir_estavel(processo)
            arquivos_saida[particao].write(json.dumps(registro_gold, ensure_ascii=False)+"\n")
            contagens[particao] += 1
    for h in arquivos_saida.values(): h.close()
    arquivo_problemas.close()
    (saida / "manifest.json").write_text(json.dumps(contagens, indent=2, ensure_ascii=False), encoding="utf-8")
    return contagens


def principal():
    p=argparse.ArgumentParser()
    p.add_argument("--gold", required=True)
    p.add_argument("--outdir", required=True)
    a=p.parse_args()
    print(json.dumps(construir_sft(a.gold,a.outdir), indent=2, ensure_ascii=False))

if __name__ == "__main__": principal()
