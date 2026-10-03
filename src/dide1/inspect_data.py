from collections import Counter
from .input_loader import iter_records
from .router import class_family
from .pipeline import is_execucao_fiscal


def inspect(path: str, sheet: str | None = None, limit: int | None = None):
    n = 0; empty = 0; execf = 0
    classes = Counter(); organs = Counter(); families = Counter()
    for rec in iter_records(path, sheet=sheet):
        if limit and n >= limit: break
        n += 1
        d = rec.data
        if not d.get("decisao", "").strip(): empty += 1
        if is_execucao_fiscal(d): execf += 1
        classes[str(d.get("classe", ""))] += 1
        organs[str(d.get("orgao_julgador", ""))] += 1
        families[class_family(d.get("classe", ""))] += 1
    return {"rows": n, "empty_decisions": empty, "execucao_fiscal": execf, "top_classes": classes.most_common(10), "top_organs": organs.most_common(10), "class_families": families.most_common(20)}
