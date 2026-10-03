import json
from pathlib import Path
from .text_utils import norm, slug


def class_family(classe: str) -> str:
    n = norm(classe)
    if "mandado de seguranca" in n: return "mandado_seguranca"
    if "cumprimento de sentenca" in n: return "cumprimento_sentenca"
    if "procedimento comum" in n: return "procedimento_comum"
    if "execucao fiscal" in n: return "execucao_fiscal"
    if "agravo" in n: return "agravo"
    if "embargos" in n: return "embargos"
    return slug(classe, 50)


def route(record: dict, config_path: str = "config/router_profiles.json") -> dict:
    fam = class_family(record.get("classe", ""))
    org = slug(record.get("orgao_julgador", ""), 80)
    region = slug(record.get("secao_subsecao", ""), 60)
    specialist = "global_teacher"
    try:
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        for profile in cfg.get("profiles", []):
            when = profile.get("when", {})
            if when.get("class_family") and when["class_family"] != fam:
                continue
            specialist = profile.get("specialist", specialist)
            break
        specialist = specialist or cfg.get("fallback", "global_teacher")
    except Exception:
        pass
    return {
        "class_family": fam,
        "region_key": region,
        "orgao_key": org,
        "route_key": f"{fam}|{region}|{org}",
        "specialist": specialist,
    }
