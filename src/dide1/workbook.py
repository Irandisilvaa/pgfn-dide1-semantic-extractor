from pathlib import Path
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import json


def _sheet(ws, rows):
    if not rows:
        return
    headers = list(rows[0].keys())
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="D9EAF7")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for idx, h in enumerate(headers, start=1):
        width = 18
        if h in {"decisao", "candidate_text", "teacher_reason", "observacao", "observacao_documento"}: width = 65
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)


def write_review_workbook(path, decisions, candidates):
    wb = Workbook()
    ws = wb.active
    ws.title = "decisoes"
    _sheet(ws, decisions)
    ws2 = wb.create_sheet("candidatos")
    _sheet(ws2, candidates)
    ws3 = wb.create_sheet("adicoes_gold")
    headers = ["source_row", "Processo", "texto_gold", "categoria_gold", "observacao", "revisor", "revisado_em"]
    ws3.append(headers)
    for c in ws3[1]: c.font = Font(bold=True)
    ws4 = wb.create_sheet("instrucoes")
    instructions = [
        ["CAMPO", "COMO USAR"],
        ["status_documento", "Marque VALIDADO_COMPLETO somente depois de ler a decisão inteira."],
        ["status_validacao", "Use APROVADO, AJUSTADO ou REJEITADO para cada candidato."],
        ["texto_ajustado", "Preencha apenas quando status_validacao=AJUSTADO."],
        ["categoria_ajustada", "Preencha apenas quando a categoria do teacher estiver incorreta."],
        ["adicoes_gold", "Adicione aqui recortes relevantes que o teacher não encontrou."],
        ["GOLD", "Somente decisões VALIDADO_COMPLETO entram na base GOLD."],
    ]
    for row in instructions: ws4.append(row)
    ws4.column_dimensions["A"].width = 28
    ws4.column_dimensions["B"].width = 90
    wb.save(Path(path))


def build_gold(review_xlsx: str, output_jsonl: str):
    wb = load_workbook(review_xlsx, data_only=True)
    decisions = wb["decisoes"]
    cand = wb["candidatos"]
    add = wb["adicoes_gold"]

    def rows_dict(ws):
        it = ws.iter_rows(values_only=True)
        headers = list(next(it))
        for row in it:
            yield {h: row[i] if i < len(row) else None for i, h in enumerate(headers)}

    dmap = {}
    for d in rows_dict(decisions):
        if str(d.get("status_documento", "")).strip().upper() == "VALIDADO_COMPLETO":
            dmap[int(d["source_row"])] = d
    gold = {k: [] for k in dmap}
    for c in rows_dict(cand):
        try: sr = int(c.get("source_row"))
        except Exception: continue
        if sr not in dmap: continue
        status = str(c.get("status_validacao", "")).strip().upper()
        if status == "APROVADO":
            text = str(c.get("candidate_text") or "")
            cat = str(c.get("teacher_category") or "")
        elif status == "AJUSTADO":
            text = str(c.get("texto_ajustado") or c.get("candidate_text") or "")
            cat = str(c.get("categoria_ajustada") or c.get("teacher_category") or "")
        else:
            continue
        if text.strip(): gold[sr].append({"text": text, "category": cat, "source": "candidate"})
    for a in rows_dict(add):
        try: sr = int(a.get("source_row"))
        except Exception: continue
        if sr in dmap and str(a.get("texto_gold") or "").strip():
            gold[sr].append({"text": str(a["texto_gold"]), "category": str(a.get("categoria_gold") or "outro_acionavel"), "source": "human_addition"})

    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for sr, d in dmap.items():
            obj = {"source_row": sr, "Processo": d.get("processo") or d.get("Processo"), "metadata": {k:v for k,v in d.items() if k not in {"decisao", "status_documento"}}, "decision": d.get("decisao", ""), "gold": gold.get(sr, [])}
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return {"validated_documents": len(dmap), "output": str(out)}
