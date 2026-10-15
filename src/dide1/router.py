import json
from pathlib import Path
from .text_utils import normalizar, gerar_slug


def familia_classe(classe: str) -> str:
    n = normalizar(classe)
    if "mandado de seguranca" in n: return "mandado_seguranca"
    if "cumprimento de sentenca" in n: return "cumprimento_sentenca"
    if "procedimento comum" in n: return "procedimento_comum"
    if "execucao fiscal" in n: return "execucao_fiscal"
    if "agravo" in n: return "agravo"
    if "embargos" in n: return "embargos"
    return gerar_slug(classe, 50)


def rotear(registro: dict, caminho_configuracao: str = "config/router_profiles.json") -> dict:
    familia = familia_classe(registro.get("classe", ""))
    orgao = gerar_slug(registro.get("orgao_julgador", ""), 80)
    regiao = gerar_slug(registro.get("secao_subsecao", ""), 60)
    especialista = "global_teacher"
    try:
        configuracao = json.loads(Path(caminho_configuracao).read_text(encoding="utf-8"))
        for perfil in configuracao.get("profiles", []):
            condicao = perfil.get("when", {})
            if condicao.get("class_family") and condicao["class_family"] != familia:
                continue
            especialista = perfil.get("specialist", especialista)
            break
        especialista = especialista or configuracao.get("fallback", "global_teacher")
    except Exception:
        pass
    return {
        "class_family": familia,
        "region_key": regiao,
        "orgao_key": orgao,
        "route_key": f"{familia}|{regiao}|{orgao}",
        "specialist": especialista,
    }
