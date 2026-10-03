from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .constants import CATEGORIES

HEADER_FILL = "D9EAF7"
REVIEW_FILL = "E2F0D9"
INPUT_FILL = "FFF2CC"
KPI_FILL = "DDEBF7"
WARN_FILL = "FCE4D6"


def _rows_dict(ws):
    it = ws.iter_rows(values_only=True)
    try:
        headers = list(next(it))
    except StopIteration:
        return
    for row in it:
        yield {h: row[i] if i < len(row) else None for i, h in enumerate(headers)}


def _style_header(ws):
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _sheet(ws, rows):
    if not rows:
        return
    headers = list(rows[0].keys())
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    _style_header(ws)
    for idx, h in enumerate(headers, start=1):
        width = 18
        if h in {
            "decisao", "candidate_text", "teacher_reason", "observacao", "observacao_documento",
            "texto_ajustado", "candidate_1_text", "candidate_2_text", "candidate_3_text",
        }:
            width = 65
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)


def _build_consolidated_rows(decisions: list[dict], candidates: list[dict], slots: int) -> list[dict]:
    decisions_by_hash: dict[str, list[dict]] = defaultdict(list)
    for d in decisions:
        h = str(d.get("decision_sha256") or f"source_row:{d.get('source_row')}")
        decisions_by_hash[h].append(d)

    candidates_by_hash: dict[str, list[dict]] = defaultdict(list)
    source_to_hash = {}
    for h, ds in decisions_by_hash.items():
        for d in ds:
            source_to_hash[str(d.get("source_row"))] = h
    for c in candidates:
        h = str(c.get("decision_sha256") or source_to_hash.get(str(c.get("source_row")), f"source_row:{c.get('source_row')}"))
        candidates_by_hash[h].append(c)

    out = []
    for h, ds in decisions_by_hash.items():
        rep = ds[0]
        source_rows = [str(d.get("source_row")) for d in ds if d.get("source_row") not in (None, "")]
        processos = sorted({str(d.get("processo") or d.get("Processo") or "") for d in ds if str(d.get("processo") or d.get("Processo") or "").strip()})
        expedientes = sorted({str(d.get("expediente") or "") for d in ds if str(d.get("expediente") or "").strip()})
        links = sorted({str(d.get("link") or "") for d in ds if str(d.get("link") or "").strip()})
        prazos = sorted({str(d.get("prazo") or "") for d in ds if str(d.get("prazo") or "").strip()})

        row = {
            "decision_sha256": h,
            "source_rows": ", ".join(source_rows),
            "ocorrencias_na_base": len(ds),
            "Processo": " | ".join(processos),
            "classe": rep.get("classe", ""),
            "origem": rep.get("origem", ""),
            "orgao_julgador": rep.get("orgao_julgador", ""),
            "data": rep.get("data", ""),
            "expedientes": " | ".join(expedientes),
            "prazos_origem": " | ".join(prazos),
            "assunto": rep.get("assunto", ""),
            "secao_subsecao": rep.get("secao_subsecao", ""),
            "nucleo": rep.get("nucleo", ""),
            "rule_id": rep.get("rule_id", ""),
            "rule_label": rep.get("rule_label", ""),
            "route_key": rep.get("route_key", ""),
            "specialist": rep.get("specialist", ""),
            "teacher_status": rep.get("teacher_status", ""),
            "teacher_attempts": rep.get("teacher_attempts", ""),
            "teacher_response_mode": rep.get("teacher_response_mode", ""),
            "cache_reutilizado": any(bool(d.get("cache_hit")) for d in ds) or len(ds) > 1,
        }

        cands = candidates_by_hash.get(h, [])
        # Cache gera linhas duplicadas por source_row. Para revisão, use apenas um conjunto por rank.
        by_rank = {}
        for c in cands:
            try:
                rank = int(c.get("candidate_rank") or 0)
            except Exception:
                rank = 0
            if rank > 0 and rank not in by_rank:
                by_rank[rank] = c

        for i in range(1, slots + 1):
            c = by_rank.get(i, {})
            row[f"candidate_{i}_text"] = c.get("candidate_text", "")
            row[f"candidate_{i}_category"] = c.get("teacher_category", "")
            row[f"candidate_{i}_priority"] = c.get("teacher_priority", "")
            row[f"candidate_{i}_reason"] = c.get("teacher_reason", "")
            row[f"candidate_{i}_status"] = ""
            row[f"candidate_{i}_texto_ajustado"] = ""
            row[f"candidate_{i}_categoria_ajustada"] = ""
            row[f"candidate_{i}_observacao"] = ""

        # Três espaços para recortes perdidos encontrados pelo humano, mantendo uma linha por decisão.
        for i in range(1, 4):
            row[f"adicao_{i}_text"] = ""
            row[f"adicao_{i}_category"] = ""

        row.update({
            "status_documento": "",
            "revisor": "",
            "revisado_em": "",
            "observacao_documento": "",
            "links_origem": " | ".join(links),
            "decisao": rep.get("decisao", ""),
        })
        out.append(row)
    return out


def _add_validation_list(ws, cell_range: str, formula: str):
    dv = DataValidation(type="list", formula1=formula, allow_blank=True)
    dv.error = "Valor fora da lista permitida."
    dv.errorTitle = "Valor inválido"
    ws.add_data_validation(dv)
    dv.add(cell_range)


def _format_consolidated(ws, slots: int, rows_count: int):
    _style_header(ws)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"

    header_map = {c.value: c.column for c in ws[1]}
    text_wide = {
        "expedientes": 35, "assunto": 28, "route_key": 30, "observacao_documento": 36,
        "links_origem": 50, "decisao": 90,
    }
    for name, width in text_wide.items():
        if name in header_map:
            ws.column_dimensions[get_column_letter(header_map[name])].width = width

    for i in range(1, slots + 1):
        for suffix, width in {
            "text": 62, "category": 24, "priority": 10, "reason": 40,
            "status": 16, "texto_ajustado": 62, "categoria_ajustada": 24, "observacao": 34,
        }.items():
            name = f"candidate_{i}_{suffix}"
            if name in header_map:
                col = get_column_letter(header_map[name])
                ws.column_dimensions[col].width = width
                if suffix in {"status", "texto_ajustado", "categoria_ajustada", "observacao"}:
                    for cell in ws[col][1:]:
                        cell.fill = PatternFill("solid", fgColor=INPUT_FILL)

    for i in range(1, 4):
        for suffix, width in {"text": 62, "category": 24}.items():
            name = f"adicao_{i}_{suffix}"
            if name in header_map:
                col = get_column_letter(header_map[name])
                ws.column_dimensions[col].width = width
                for cell in ws[col][1:]:
                    cell.fill = PatternFill("solid", fgColor=INPUT_FILL)

    for name in ("status_documento", "revisor", "revisado_em", "observacao_documento"):
        if name in header_map:
            col = get_column_letter(header_map[name])
            ws.column_dimensions[col].width = 24 if name != "observacao_documento" else 36
            for cell in ws[col][1:]:
                cell.fill = PatternFill("solid", fgColor=REVIEW_FILL)

    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)

    if rows_count:
        end = rows_count + 1
        _add_validation_list(ws, f"{get_column_letter(header_map['status_documento'])}2:{get_column_letter(header_map['status_documento'])}{end}", "=listas!$C$2:$C$3")
        for i in range(1, slots + 1):
            status_col = get_column_letter(header_map[f"candidate_{i}_status"])
            cat_col = get_column_letter(header_map[f"candidate_{i}_categoria_ajustada"])
            _add_validation_list(ws, f"{status_col}2:{status_col}{end}", "=listas!$A$2:$A$4")
            _add_validation_list(ws, f"{cat_col}2:{cat_col}{end}", f"=listas!$B$2:$B${len(CATEGORIES)+1}")
        for i in range(1, 4):
            cat_col = get_column_letter(header_map[f"adicao_{i}_category"])
            _add_validation_list(ws, f"{cat_col}2:{cat_col}{end}", f"=listas!$B$2:$B${len(CATEGORIES)+1}")

        status_doc_col = get_column_letter(header_map["status_documento"])
        ws.conditional_formatting.add(
            f"{status_doc_col}2:{status_doc_col}{end}",
            FormulaRule(formula=[f'${status_doc_col}2="VALIDADO_COMPLETO"'], fill=PatternFill("solid", fgColor="C6EFCE")),
        )


def _build_metrics_sheet(ws, review_ws, slots: int, review_rows: int):
    ws.sheet_view.showGridLines = False
    ws["A1"] = "DIDE1 — Métricas de qualidade após revisão humana"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:D1")
    ws["A2"] = "As métricas de qualidade só são interpretáveis depois que os procuradores revisarem os candidatos e marcarem VALIDADO_COMPLETO."
    ws.merge_cells("A2:D2")
    ws["A2"].fill = PatternFill("solid", fgColor=WARN_FILL)
    ws["A2"].alignment = Alignment(wrap_text=True)

    h = {c.value: get_column_letter(c.column) for c in review_ws[1]}
    end = max(2, review_rows + 1)
    sh = "'revisao_consolidada'"

    def count_status(value: str) -> str:
        parts = []
        for i in range(1, slots + 1):
            col = h[f"candidate_{i}_status"]
            parts.append(f'COUNTIF({sh}!${col}$2:${col}${end},"{value}")')
        return "=" + "+".join(parts)

    def count_nonblank(prefix: str, suffix: str, nslots: int) -> str:
        parts = []
        for i in range(1, nslots + 1):
            col = h[f"{prefix}_{i}_{suffix}"]
            parts.append(f'COUNTIF({sh}!${col}$2:${col}${end},"<>")')
        return "=" + "+".join(parts)

    metrics = [
        ("Documentos únicos no lote", f"=COUNTA({sh}!${h['decision_sha256']}$2:${h['decision_sha256']}${end})"),
        ("Ocorrências/expedientes cobertos", f"=SUM({sh}!${h['ocorrencias_na_base']}$2:${h['ocorrencias_na_base']}${end})"),
        ("Documentos VALIDADO_COMPLETO", f'=COUNTIF({sh}!${h["status_documento"]}$2:${h}!${h["status_documento"]}${end},"VALIDADO_COMPLETO")' if False else f'=COUNTIF({sh}!${h["status_documento"]}$2:${h["status_documento"]}${end},"VALIDADO_COMPLETO")'),
        ("Candidatos propostos", count_nonblank("candidate", "text", slots)),
        ("Candidatos APROVADOS", count_status("APROVADO")),
        ("Candidatos AJUSTADOS", count_status("AJUSTADO")),
        ("Candidatos REJEITADOS", count_status("REJEITADO")),
        ("Adições humanas (misses)", count_nonblank("adicao", "text", 3)),
        ("Docs com RULE_FALLBACK", f'=COUNTIF({sh}!${h["teacher_status"]}$2:${h["teacher_status"]}${end},"RULE_FALLBACK*")'),
        ("Docs EMPTY_VALID", f'=COUNTIF({sh}!${h["teacher_status"]}$2:${h["teacher_status"]}${end},"EMPTY_VALID")'),
        ("Docs ERROR", f'=COUNTIF({sh}!${h["teacher_status"]}$2:${h["teacher_status"]}${end},"ERROR")'),
    ]

    ws.append([])
    ws.append(["MÉTRICA", "VALOR", "COMO INTERPRETAR"])
    header_row = ws.max_row
    for c in ws[header_row]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=HEADER_FILL)

    interpretations = {
        "Documentos únicos no lote": "Uma linha por decisão única (SHA-256).",
        "Ocorrências/expedientes cobertos": "Quantidade de linhas da base representadas pelas decisões únicas.",
        "Documentos VALIDADO_COMPLETO": "Só estes documentos podem entrar no GOLD.",
        "Candidatos propostos": "Recortes produzidos pelo teacher.",
        "Candidatos APROVADOS": "Recortes corretos sem ajuste.",
        "Candidatos AJUSTADOS": "Teacher encontrou algo útil, mas o humano corrigiu texto e/ou categoria.",
        "Candidatos REJEITADOS": "Falsos positivos.",
        "Adições humanas (misses)": "Recortes relevantes que o teacher não encontrou.",
        "Docs com RULE_FALLBACK": "Casos em que o teacher falhou e houve recuperação determinística; revisar com atenção.",
        "Docs EMPTY_VALID": "Teacher concluiu que não havia recorte válido; confirmar lendo a decisão inteira.",
        "Docs ERROR": "Falhas fatais; meta operacional é zero.",
    }
    for name, formula in metrics:
        ws.append([name, formula, interpretations[name]])

    # Índices fixos das métricas acima na coluna B.
    metric_rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1)}
    approved = f"B{metric_rows['Candidatos APROVADOS']}"
    adjusted = f"B{metric_rows['Candidatos AJUSTADOS']}"
    rejected = f"B{metric_rows['Candidatos REJEITADOS']}"
    additions = f"B{metric_rows['Adições humanas (misses)']}"
    validated = f"B{metric_rows['Documentos VALIDADO_COMPLETO']}"

    ws.append([])
    ws.append(["INDICADOR DE QUALIDADE", "VALOR", "DEFINIÇÃO"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=KPI_FILL)

    strict_precision = f'=IFERROR({approved}/({approved}+{adjusted}+{rejected}),"")'
    useful_rate = f'=IFERROR(({approved}+{adjusted})/({approved}+{adjusted}+{rejected}),"")'
    recall = f'=IFERROR(({approved}+{adjusted})/({approved}+{adjusted}+{additions}),"")'
    q_header_row = ws.max_row
    precision_row = q_header_row + 1
    recall_row = q_header_row + 3
    f1 = f'=IFERROR(2*B{precision_row}*B{recall_row}/(B{precision_row}+B{recall_row}),"")'

    # Category correctness: approved + adjusted without category correction / useful candidates.
    cat_correct_parts = []
    for i in range(1, slots + 1):
        status_col = h[f"candidate_{i}_status"]
        adj_cat_col = h[f"candidate_{i}_categoria_ajustada"]
        cat_correct_parts.append(f'COUNTIF({sh}!${status_col}$2:${status_col}${end},"APROVADO")')
        cat_correct_parts.append(f'COUNTIFS({sh}!${status_col}$2:${status_col}${end},"AJUSTADO",{sh}!${adj_cat_col}$2:${adj_cat_col}${end},"")')
    category_accuracy = f'=IFERROR(({"+".join(cat_correct_parts)})/({approved}+{adjusted}),"")'

    # Complete coverage = validated docs without human additions.
    add_cols = [h[f"adicao_{i}_text"] for i in range(1, 4)]
    complete_formula = (
        f'=IFERROR(SUMPRODUCT(--({sh}!${h["status_documento"]}$2:${h["status_documento"]}${end}="VALIDADO_COMPLETO"),'
        + ",".join(f'--({sh}!${c}$2:${c}${end}="")' for c in add_cols)
        + f')/{validated},"")'
    )

    quality_rows = [
        ("Precisão estrita", strict_precision, "APROVADO / (APROVADO + AJUSTADO + REJEITADO)."),
        ("Taxa útil", useful_rate, "(APROVADO + AJUSTADO) / candidatos revisados."),
        ("Recall estimado", recall, "Recortes úteis encontrados / (recortes úteis encontrados + adições humanas)."),
        ("F1 estimado", f1, "Média harmônica entre precisão estrita e recall estimado."),
        ("Acurácia de categoria", category_accuracy, "Entre recortes úteis, proporção sem correção de categoria."),
        ("Cobertura completa por decisão", complete_formula, "VALIDADO_COMPLETO sem necessidade de adição humana / documentos validados."),
    ]
    q_start = ws.max_row + 1
    for name, formula, definition in quality_rows:
        ws.append([name, formula, definition])
    for r in range(q_start, ws.max_row + 1):
        ws.cell(r, 2).number_format = "0.0%"

    # Distribuição por categoria para inspeção rápida.
    ws.append([])
    ws.append(["CATEGORIA", "PROPOSTOS", "APROVADOS", "AJUSTADOS", "REJEITADOS"])
    dist_header = ws.max_row
    for c in ws[dist_header]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=HEADER_FILL)
    for cat in CATEGORIES:
        proposed_parts = []
        app_parts = []
        adj_parts = []
        rej_parts = []
        for i in range(1, slots + 1):
            cat_col = h[f"candidate_{i}_category"]
            status_col = h[f"candidate_{i}_status"]
            proposed_parts.append(f'COUNTIF({sh}!${cat_col}$2:${cat_col}${end},A{ws.max_row+1})')
            app_parts.append(f'COUNTIFS({sh}!${cat_col}$2:${cat_col}${end},A{ws.max_row+1},{sh}!${status_col}$2:${status_col}${end},"APROVADO")')
            adj_parts.append(f'COUNTIFS({sh}!${cat_col}$2:${cat_col}${end},A{ws.max_row+1},{sh}!${status_col}$2:${status_col}${end},"AJUSTADO")')
            rej_parts.append(f'COUNTIFS({sh}!${cat_col}$2:${cat_col}${end},A{ws.max_row+1},{sh}!${status_col}$2:${status_col}${end},"REJEITADO")')
        row_num = ws.max_row + 1
        ws.append([
            cat,
            "=" + "+".join(x.replace(f"A{row_num}", f"A{row_num}") for x in proposed_parts),
            "=" + "+".join(x.replace(f"A{row_num}", f"A{row_num}") for x in app_parts),
            "=" + "+".join(x.replace(f"A{row_num}", f"A{row_num}") for x in adj_parts),
            "=" + "+".join(x.replace(f"A{row_num}", f"A{row_num}") for x in rej_parts),
        ])

    ws.column_dimensions["A"].width = 36
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 90
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 16
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A4"


def write_review_workbook(path, decisions, candidates):
    slots = max(3, max([int(c.get("candidate_rank") or 0) for c in candidates] or [0]))
    consolidated = _build_consolidated_rows(decisions, candidates, slots)

    wb = Workbook()
    review = wb.active
    review.title = "revisao_consolidada"
    _sheet(review, consolidated)
    _format_consolidated(review, slots, len(consolidated))

    metrics = wb.create_sheet("metricas")
    _build_metrics_sheet(metrics, review, slots, len(consolidated))

    instr = wb.create_sheet("instrucoes")
    instructions = [
        ["CAMPO", "COMO USAR"],
        ["revisao_consolidada", "É a aba principal. Há uma linha por decisão única (SHA-256), mesmo que a decisão apareça em vários expedientes."],
        ["candidate_N_status", "Para cada recorte: APROVADO, AJUSTADO ou REJEITADO. Não escolha apenas o melhor: aprove todos os recortes juridicamente relevantes."],
        ["candidate_N_texto_ajustado", "Preencha quando status=AJUSTADO e o limite/texto do recorte precisar ser corrigido."],
        ["candidate_N_categoria_ajustada", "Preencha somente quando a categoria do teacher estiver incorreta."],
        ["adicao_N_text/category", "Use quando a decisão contém um recorte relevante que o teacher não encontrou. Há três espaços na linha; para mais, use adicoes_gold."],
        ["status_documento", "Marque VALIDADO_COMPLETO somente após ler a decisão integral e revisar todos os candidatos/omissões."],
        ["metricas", "Atualiza conforme a revisão humana. Precisão/recall/F1 não devem ser interpretados antes de haver documentos VALIDADO_COMPLETO."],
        ["candidatos / decisoes", "Abas de auditoria técnica. Não são a interface principal de revisão humana."],
        ["GOLD", "build-gold lê preferencialmente revisao_consolidada e deduplica decisões idênticas."],
    ]
    for row in instructions:
        instr.append(row)
    _style_header(instr)
    instr.column_dimensions["A"].width = 34
    instr.column_dimensions["B"].width = 110
    for row in instr.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)

    dec = wb.create_sheet("decisoes")
    _sheet(dec, decisions)
    cand = wb.create_sheet("candidatos")
    _sheet(cand, candidates)

    add = wb.create_sheet("adicoes_gold")
    headers = ["decision_sha256", "source_row", "Processo", "texto_gold", "categoria_gold", "observacao", "revisor", "revisado_em"]
    add.append(headers)
    _style_header(add)
    add.column_dimensions["D"].width = 80
    add.column_dimensions["E"].width = 28

    listas = wb.create_sheet("listas")
    listas.append(["status_candidato", "categoria", "status_documento"])
    max_len = max(3, len(CATEGORIES))
    candidate_status = ["APROVADO", "AJUSTADO", "REJEITADO"]
    doc_status = ["PENDENTE_REVISAO", "VALIDADO_COMPLETO"]
    for i in range(max_len):
        listas.append([
            candidate_status[i] if i < len(candidate_status) else "",
            CATEGORIES[i] if i < len(CATEGORIES) else "",
            doc_status[i] if i < len(doc_status) else "",
        ])
    listas.sheet_state = "hidden"

    wb.active = wb.sheetnames.index("revisao_consolidada")
    wb.save(Path(path))


def _build_gold_from_consolidated(wb, output_jsonl: str):
    review = wb["revisao_consolidada"]
    rows = list(_rows_dict(review))
    # Detecta quantos slots existem pelo cabeçalho.
    headers = [c.value for c in review[1]]
    slots = 0
    while f"candidate_{slots+1}_text" in headers:
        slots += 1

    extra_additions = defaultdict(list)
    if "adicoes_gold" in wb.sheetnames:
        for a in _rows_dict(wb["adicoes_gold"]):
            text = str(a.get("texto_gold") or "").strip()
            if not text:
                continue
            h = str(a.get("decision_sha256") or "").strip()
            sr = str(a.get("source_row") or "").strip()
            key = h or f"source_row:{sr}"
            extra_additions[key].append({
                "text": text,
                "category": str(a.get("categoria_gold") or "outro_acionavel"),
                "source": "human_addition",
            })

    validated = []
    for r in rows:
        if str(r.get("status_documento") or "").strip().upper() != "VALIDADO_COMPLETO":
            continue
        gold = []
        for i in range(1, slots + 1):
            status = str(r.get(f"candidate_{i}_status") or "").strip().upper()
            if status == "APROVADO":
                text = str(r.get(f"candidate_{i}_text") or "")
                cat = str(r.get(f"candidate_{i}_category") or "")
            elif status == "AJUSTADO":
                text = str(r.get(f"candidate_{i}_texto_ajustado") or r.get(f"candidate_{i}_text") or "")
                cat = str(r.get(f"candidate_{i}_categoria_ajustada") or r.get(f"candidate_{i}_category") or "")
            else:
                continue
            if text.strip():
                gold.append({"text": text, "category": cat, "source": "candidate"})

        for i in range(1, 4):
            text = str(r.get(f"adicao_{i}_text") or "").strip()
            if text:
                gold.append({
                    "text": text,
                    "category": str(r.get(f"adicao_{i}_category") or "outro_acionavel"),
                    "source": "human_addition",
                })

        h = str(r.get("decision_sha256") or "")
        source_rows = [x.strip() for x in str(r.get("source_rows") or "").split(",") if x.strip()]
        for key in (h, *(f"source_row:{sr}" for sr in source_rows)):
            if key in extra_additions:
                gold.extend(extra_additions[key])

        obj = {
            "source_row": int(source_rows[0]) if source_rows and source_rows[0].isdigit() else (source_rows[0] if source_rows else None),
            "source_rows": source_rows,
            "decision_sha256": h,
            "Processo": r.get("Processo"),
            "metadata": {
                "classe": r.get("classe", ""),
                "origem": r.get("origem", ""),
                "orgao_julgador": r.get("orgao_julgador", ""),
                "data": r.get("data", ""),
                "expediente": r.get("expedientes", ""),
                "prazo": r.get("prazos_origem", ""),
                "assunto": r.get("assunto", ""),
                "secao_subsecao": r.get("secao_subsecao", ""),
                "nucleo": r.get("nucleo", ""),
                "route_key": r.get("route_key", ""),
                "specialist": r.get("specialist", ""),
            },
            "decision": r.get("decisao", ""),
            "gold": gold,
        }
        validated.append(obj)

    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for obj in validated:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    return {"validated_documents": len(validated), "output": str(out), "source": "revisao_consolidada"}


def build_gold(review_xlsx: str, output_jsonl: str):
    wb = load_workbook(review_xlsx, data_only=True)
    if "revisao_consolidada" in wb.sheetnames:
        return _build_gold_from_consolidated(wb, output_jsonl)

    # Compatibilidade com workbooks v4.0/v4.1.
    decisions = wb["decisoes"]
    cand = wb["candidatos"]
    add = wb["adicoes_gold"]

    dmap = {}
    for d in _rows_dict(decisions):
        if str(d.get("status_documento", "")).strip().upper() == "VALIDADO_COMPLETO":
            dmap[int(d["source_row"])] = d
    gold = {k: [] for k in dmap}
    for c in _rows_dict(cand):
        try:
            sr = int(c.get("source_row"))
        except Exception:
            continue
        if sr not in dmap:
            continue
        status = str(c.get("status_validacao", "")).strip().upper()
        if status == "APROVADO":
            text = str(c.get("candidate_text") or "")
            cat = str(c.get("teacher_category") or "")
        elif status == "AJUSTADO":
            text = str(c.get("texto_ajustado") or c.get("candidate_text") or "")
            cat = str(c.get("categoria_ajustada") or c.get("teacher_category") or "")
        else:
            continue
        if text.strip():
            gold[sr].append({"text": text, "category": cat, "source": "candidate"})
    for a in _rows_dict(add):
        try:
            sr = int(a.get("source_row"))
        except Exception:
            continue
        if sr in dmap and str(a.get("texto_gold") or "").strip():
            gold[sr].append({
                "text": str(a["texto_gold"]),
                "category": str(a.get("categoria_gold") or "outro_acionavel"),
                "source": "human_addition",
            })

    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for sr, d in dmap.items():
            obj = {
                "source_row": sr,
                "Processo": d.get("processo") or d.get("Processo"),
                "metadata": {k: v for k, v in d.items() if k not in {"decisao", "status_documento"}},
                "decision": d.get("decisao", ""),
                "gold": gold.get(sr, []),
            }
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
    return {"validated_documents": len(dmap), "output": str(out), "source": "legacy"}
