from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import csv
import json

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .constants import CATEGORIES

HEADER_FILL = "1F4E78"
HEADER_FONT = "FFFFFF"
CONTEXT_FILL = "D9EAF7"
CANDIDATE_FILL = "E2F0D9"
HUMAN_FILL = "FFF2CC"
STATUS_FILL = "EDEDED"
KPI_FILL = "DDEBF7"
WARN_FILL = "FCE4D6"
GREEN_FILL = "C6EFCE"
ORANGE_FILL = "FCE4D6"
RED_FILL = "FFC7CE"
YELLOW_FILL = "FFF2CC"

CANDIDATE_STATUS = ["PENDENTE", "APROVADO", "AJUSTADO", "REJEITADO"]
DOCUMENT_STATUS = ["PENDENTE_REVISAO", "VALIDADO_COMPLETO"]


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
        cell.font = Font(bold=True, color=HEADER_FONT)
        cell.fill = PatternFill("solid", fgColor=HEADER_FILL)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def _add_validation_list(ws, cell_range: str, formula: str):
    dv = DataValidation(type="list", formula1=formula, allow_blank=False)
    dv.error = "Escolha um valor da lista."
    dv.errorTitle = "Valor inválido"
    dv.prompt = "Selecione uma das opções disponíveis."
    dv.promptTitle = "Preenchimento padronizado"
    dv.showInputMessage = True
    dv.showErrorMessage = True
    ws.add_data_validation(dv)
    dv.add(cell_range)


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
        if h in {"decisao", "candidate_text", "teacher_reason", "observacao", "observacao_documento", "texto_ajustado"}:
            width = 55
        ws.column_dimensions[get_column_letter(idx)].width = width
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=False)


def _decision_key(d: dict) -> str:
    return str(d.get("decision_sha256") or f"source_row:{d.get('source_row')}")


def _build_groups(decisions: list[dict], candidates: list[dict]):
    decisions_by_hash: dict[str, list[dict]] = defaultdict(list)
    for d in decisions:
        decisions_by_hash[_decision_key(d)].append(d)

    source_to_hash = {}
    for h, ds in decisions_by_hash.items():
        for d in ds:
            source_to_hash[str(d.get("source_row"))] = h

    candidates_by_hash: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        h = str(c.get("decision_sha256") or source_to_hash.get(str(c.get("source_row")), f"source_row:{c.get('source_row')}"))
        candidates_by_hash[h].append(c)
    return decisions_by_hash, candidates_by_hash


def _prior_annotations(prior_rows: list[dict] | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for r in prior_rows or []:
        h = str(r.get("_decision_sha256") or r.get("decision_sha256") or "").strip()
        if h:
            out[h] = r
    return out


def _build_review_rows(
    decisions: list[dict],
    candidates: list[dict],
    slots: int,
    prior_rows: list[dict] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Cria a interface humana compacta e uma tabela técnica 1:1 por decisão.

    A interface mostra apenas contexto necessário + recortes/categorias editáveis + dropdowns.
    Toda a proveniência fica em dados_tecnicos, escondida dos revisores.
    """
    decisions_by_hash, candidates_by_hash = _build_groups(decisions, candidates)
    prior = _prior_annotations(prior_rows)

    review_rows: list[dict] = []
    technical_rows: list[dict] = []

    for seq, (h, ds) in enumerate(decisions_by_hash.items(), start=1):
        rep = ds[0]
        decision_id = f"D{seq:04d}"
        source_rows = [str(d.get("source_row")) for d in ds if d.get("source_row") not in (None, "")]
        processos = sorted({str(d.get("processo") or d.get("Processo") or "") for d in ds if str(d.get("processo") or d.get("Processo") or "").strip()})
        expedientes = sorted({str(d.get("expediente") or "") for d in ds if str(d.get("expediente") or "").strip()})
        prazos = sorted({str(d.get("prazo") or "") for d in ds if str(d.get("prazo") or "").strip()})
        links = sorted({str(d.get("link") or "") for d in ds if str(d.get("link") or "").strip()})

        cands = candidates_by_hash.get(h, [])
        by_rank: dict[int, dict] = {}
        for c in cands:
            try:
                rank = int(c.get("candidate_rank") or 0)
            except Exception:
                rank = 0
            if rank > 0 and rank not in by_rank:
                by_rank[rank] = c

        old = prior.get(h, {})
        review = {
            "_decision_sha256": h,
            "ID": decision_id,
            "Processo": " | ".join(processos),
            "Classe": rep.get("classe", ""),
            "Órgão julgador": rep.get("orgao_julgador", ""),
            "Expediente": " | ".join(expedientes),
            "Prazo": " | ".join(prazos),
            "Assunto": rep.get("assunto", ""),
        }

        # Candidatos: texto/categoria já são os campos finais editáveis.
        for i in range(1, slots + 1):
            c = by_rank.get(i, {})
            original_text = str(c.get("candidate_text") or "")
            original_cat = str(c.get("teacher_category") or "")

            # Migração transparente da v4.2: preserva correções já feitas.
            old_status = str(old.get(f"candidate_{i}_status") or old.get(f"validacao_{i}") or "").strip().upper()
            old_adjusted_text = str(old.get(f"candidate_{i}_texto_ajustado") or "").strip()
            old_adjusted_cat = str(old.get(f"candidate_{i}_categoria_ajustada") or "").strip()
            old_direct_text = old.get(f"recorte_{i}")
            old_direct_cat = old.get(f"categoria_{i}")

            final_text = str(old_direct_text if old_direct_text not in (None, "") else (old_adjusted_text if old_status == "AJUSTADO" and old_adjusted_text else original_text))
            final_cat = str(old_direct_cat if old_direct_cat not in (None, "") else (old_adjusted_cat if old_status == "AJUSTADO" and old_adjusted_cat else original_cat))

            if original_text:
                status = old_status if old_status in CANDIDATE_STATUS else "PENDENTE"
            else:
                status = ""

            review[f"Recorte {i}"] = final_text
            review[f"Categoria {i}"] = final_cat
            review[f"Validação {i}"] = status

        # Apenas dois espaços extras na tela principal; casos raros adicionais usam adicoes_gold.
        for i in range(1, 3):
            review[f"Recorte ausente {i}"] = str(old.get(f"adicao_{i}_text") or old.get(f"Recorte ausente {i}") or "")
            review[f"Categoria ausente {i}"] = str(old.get(f"adicao_{i}_category") or old.get(f"Categoria ausente {i}") or "")

        old_doc_status = str(old.get("status_documento") or old.get("Status da decisão") or "").strip().upper()
        review.update({
            "Status da decisão": old_doc_status if old_doc_status in DOCUMENT_STATUS else "PENDENTE_REVISAO",
            "Revisor": str(old.get("revisor") or old.get("Revisor") or ""),
            "Observação": str(old.get("observacao_documento") or old.get("Observação") or ""),
        })
        review_rows.append(review)

        technical = {
            "_decision_sha256": h,
            "ID": decision_id,
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
            "links_origem": " | ".join(links),
            "decisao": rep.get("decisao", ""),
        }
        for i in range(1, slots + 1):
            c = by_rank.get(i, {})
            technical[f"teacher_text_{i}"] = c.get("candidate_text", "")
            technical[f"teacher_category_{i}"] = c.get("teacher_category", "")
            technical[f"teacher_priority_{i}"] = c.get("teacher_priority", "")
            technical[f"teacher_reason_{i}"] = c.get("teacher_reason", "")
        technical_rows.append(technical)

    return review_rows, technical_rows


def _format_review(ws, slots: int, rows_count: int):
    _style_header(ws)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "C2"

    header_map = {c.value: c.column for c in ws[1]}

    # Coluna de hash existe para ligação técnica, mas fica invisível para o procurador.
    if "_decision_sha256" in header_map:
        ws.column_dimensions[get_column_letter(header_map["_decision_sha256"])].hidden = True

    widths = {
        "ID": 9,
        "Processo": 25,
        "Classe": 16,
        "Órgão julgador": 24,
        "Expediente": 28,
        "Prazo": 12,
        "Assunto": 28,
        "Status da decisão": 20,
        "Revisor": 20,
        "Observação": 32,
    }
    for name, width in widths.items():
        if name in header_map:
            ws.column_dimensions[get_column_letter(header_map[name])].width = width

    for i in range(1, slots + 1):
        for name, width in {
            f"Recorte {i}": 48,
            f"Categoria {i}": 24,
            f"Validação {i}": 15,
        }.items():
            if name in header_map:
                ws.column_dimensions[get_column_letter(header_map[name])].width = width

    for i in range(1, 3):
        for name, width in {
            f"Recorte ausente {i}": 42,
            f"Categoria ausente {i}": 24,
        }.items():
            if name in header_map:
                ws.column_dimensions[get_column_letter(header_map[name])].width = width

    # Altura fixa: evita que textos longos criem linhas gigantes.
    for r in range(2, rows_count + 2):
        ws.row_dimensions[r].height = 54

    # Sem wrap por padrão; campos de texto de revisão usam wrap dentro da altura fixa.
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=False)

    wrap_names = ["Assunto", "Observação"]
    for i in range(1, slots + 1):
        wrap_names.append(f"Recorte {i}")
    for i in range(1, 3):
        wrap_names.append(f"Recorte ausente {i}")
    for name in wrap_names:
        if name in header_map:
            col = get_column_letter(header_map[name])
            for c in ws[col][1:]:
                c.alignment = Alignment(vertical="top", wrap_text=True)

    # Cores por blocos para leitura rápida.
    context_names = ["ID", "Processo", "Classe", "Órgão julgador", "Expediente", "Prazo", "Assunto"]
    for name in context_names:
        if name in header_map:
            col = get_column_letter(header_map[name])
            for c in ws[col][1:]:
                c.fill = PatternFill("solid", fgColor=CONTEXT_FILL)

    for i in range(1, slots + 1):
        for name in (f"Recorte {i}", f"Categoria {i}", f"Validação {i}"):
            if name in header_map:
                col = get_column_letter(header_map[name])
                for c in ws[col][1:]:
                    c.fill = PatternFill("solid", fgColor=CANDIDATE_FILL)

    for i in range(1, 3):
        for name in (f"Recorte ausente {i}", f"Categoria ausente {i}"):
            if name in header_map:
                col = get_column_letter(header_map[name])
                for c in ws[col][1:]:
                    c.fill = PatternFill("solid", fgColor=HUMAN_FILL)

    for name in ("Status da decisão", "Revisor", "Observação"):
        if name in header_map:
            col = get_column_letter(header_map[name])
            for c in ws[col][1:]:
                c.fill = PatternFill("solid", fgColor=STATUS_FILL)

    if rows_count:
        end = rows_count + 1
        for i in range(1, slots + 1):
            cat = get_column_letter(header_map[f"Categoria {i}"])
            status = get_column_letter(header_map[f"Validação {i}"])
            _add_validation_list(ws, f"{cat}2:{cat}{end}", f"=listas!$B$2:$B${len(CATEGORIES)+1}")
            # Status só é obrigatório para linhas que têm candidato; linhas vazias permanecem vazias.
            dv = DataValidation(type="list", formula1="=listas!$A$2:$A$5", allow_blank=True)
            dv.error = "Escolha PENDENTE, APROVADO, AJUSTADO ou REJEITADO."
            dv.showErrorMessage = True
            ws.add_data_validation(dv)
            dv.add(f"{status}2:{status}{end}")

            # Cores do dropdown de validação.
            ws.conditional_formatting.add(
                f"{status}2:{status}{end}",
                FormulaRule(formula=[f'${status}2="APROVADO"'], fill=PatternFill("solid", fgColor=GREEN_FILL)),
            )
            ws.conditional_formatting.add(
                f"{status}2:{status}{end}",
                FormulaRule(formula=[f'${status}2="AJUSTADO"'], fill=PatternFill("solid", fgColor=ORANGE_FILL)),
            )
            ws.conditional_formatting.add(
                f"{status}2:{status}{end}",
                FormulaRule(formula=[f'${status}2="REJEITADO"'], fill=PatternFill("solid", fgColor=RED_FILL)),
            )
            ws.conditional_formatting.add(
                f"{status}2:{status}{end}",
                FormulaRule(formula=[f'${status}2="PENDENTE"'], fill=PatternFill("solid", fgColor=YELLOW_FILL)),
            )

        for i in range(1, 3):
            cat = get_column_letter(header_map[f"Categoria ausente {i}"])
            dv = DataValidation(type="list", formula1=f"=listas!$B$2:$B${len(CATEGORIES)+1}", allow_blank=True)
            dv.showErrorMessage = True
            ws.add_data_validation(dv)
            dv.add(f"{cat}2:{cat}{end}")

        doc_status = get_column_letter(header_map["Status da decisão"])
        _add_validation_list(ws, f"{doc_status}2:{doc_status}{end}", "=listas!$C$2:$C$3")
        ws.conditional_formatting.add(
            f"{doc_status}2:{doc_status}{end}",
            FormulaRule(formula=[f'${doc_status}2="VALIDADO_COMPLETO"'], fill=PatternFill("solid", fgColor=GREEN_FILL)),
        )

        # Alerta visual: não marcar documento completo enquanto algum candidato ainda estiver PENDENTE.
        pending_checks = []
        for i in range(1, slots + 1):
            txt_col = get_column_letter(header_map[f"Recorte {i}"])
            val_col = get_column_letter(header_map[f"Validação {i}"])
            pending_checks.append(f'AND(${txt_col}2<>"",${val_col}2="PENDENTE")')
        if pending_checks:
            formula = f'=AND(${doc_status}2="VALIDADO_COMPLETO",OR({",".join(pending_checks)}))'
            ws.conditional_formatting.add(
                f"A2:{get_column_letter(ws.max_column)}{end}",
                FormulaRule(formula=[formula], fill=PatternFill("solid", fgColor=RED_FILL)),
            )


def _build_reading_sheet(ws, technical_rows: list[dict]):
    rows = []
    for t in technical_rows:
        rows.append({
            "ID": t.get("ID", ""),
            "Processo": t.get("Processo", ""),
            "Classe": t.get("classe", ""),
            "Assunto": t.get("assunto", ""),
            "Decisão completa": t.get("decisao", ""),
        })
    _sheet(ws, rows)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A2"
    widths = {"A": 10, "B": 26, "C": 18, "D": 28, "E": 100}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    for r in range(2, ws.max_row + 1):
        ws.row_dimensions[r].height = 110
        ws.cell(r, 5).alignment = Alignment(vertical="top", wrap_text=True)


def _build_metrics_sheet(ws, review_ws, tech_ws, slots: int, review_rows: int):
    ws.sheet_view.showGridLines = False
    ws["A1"] = "DIDE1 — Qualidade após revisão humana"
    ws["A1"].font = Font(bold=True, size=14)
    ws.merge_cells("A1:D1")
    ws["A2"] = "As métricas só são confiáveis depois que o procurador revisa a decisão inteira e marca VALIDADO_COMPLETO."
    ws.merge_cells("A2:D2")
    ws["A2"].fill = PatternFill("solid", fgColor=WARN_FILL)
    ws["A2"].alignment = Alignment(wrap_text=True)

    h = {c.value: get_column_letter(c.column) for c in review_ws[1]}
    end = max(2, review_rows + 1)
    sh = "'revisao'"

    def sum_status(value: str) -> str:
        parts = []
        for i in range(1, slots + 1):
            c = h[f"Validação {i}"]
            parts.append(f'COUNTIF({sh}!${c}$2:${c}${end},"{value}")')
        return "=" + "+".join(parts)

    candidate_nonblank = []
    for i in range(1, slots + 1):
        c = h[f"Recorte {i}"]
        candidate_nonblank.append(f'COUNTIF({sh}!${c}$2:${c}${end},"<>")')

    addition_nonblank = []
    for i in range(1, 3):
        c = h[f"Recorte ausente {i}"]
        addition_nonblank.append(f'COUNTIF({sh}!${c}$2:${c}${end},"<>")')

    rows = [
        ["MÉTRICA", "VALOR", "INTERPRETAÇÃO"],
        ["Decisões únicas", f'=COUNTA({sh}!${h["ID"]}$2:${h["ID"]}${end})', "Uma linha por decisão única."],
        ["Decisões VALIDADO_COMPLETO", f'=COUNTIF({sh}!${h["Status da decisão"]}$2:${h["Status da decisão"]}${end},"VALIDADO_COMPLETO")', "Entram no GOLD somente após revisão completa."],
        ["Candidatos propostos", "=" + "+".join(candidate_nonblank), "Recortes sugeridos pelo teacher."],
        ["APROVADOS", sum_status("APROVADO"), "Corretos sem alteração humana."],
        ["AJUSTADOS", sum_status("AJUSTADO"), "Úteis, mas o procurador editou texto e/ou categoria."],
        ["REJEITADOS", sum_status("REJEITADO"), "Falsos positivos."],
        ["PENDENTES", sum_status("PENDENTE"), "Ainda não revisados."],
        ["Adições humanas", "=" + "+".join(addition_nonblank), "Recortes relevantes que o modelo deixou escapar."],
    ]
    for row in rows:
        ws.append(row)
    for c in ws[3]:
        c.fill = PatternFill("solid", fgColor=HEADER_FILL)
        c.font = Font(bold=True, color=HEADER_FONT)

    metric_rows = {ws.cell(r, 1).value: r for r in range(1, ws.max_row + 1)}
    app = f"B{metric_rows['APROVADOS']}"
    adj = f"B{metric_rows['AJUSTADOS']}"
    rej = f"B{metric_rows['REJEITADOS']}"
    adds = f"B{metric_rows['Adições humanas']}"
    validated = f"B{metric_rows['Decisões VALIDADO_COMPLETO']}"

    ws.append([])
    ws.append(["INDICADOR", "VALOR", "DEFINIÇÃO"])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True, color="000000")
        c.fill = PatternFill("solid", fgColor=KPI_FILL)

    precision_row = ws.max_row + 1
    quality = [
        ["Precisão estrita", f'=IFERROR({app}/({app}+{adj}+{rej}),"")', "Aprovados / candidatos efetivamente revisados."],
        ["Taxa útil", f'=IFERROR(({app}+{adj})/({app}+{adj}+{rej}),"")', "Aprovados + ajustados / revisados."],
        ["Recall estimado", f'=IFERROR(({app}+{adj})/({app}+{adj}+{adds}),"")', "Recortes úteis encontrados / encontrados + adições humanas."],
    ]
    for row in quality:
        ws.append(row)
    recall_row = precision_row + 2
    ws.append(["F1 estimado", f'=IFERROR(2*B{precision_row}*B{recall_row}/(B{precision_row}+B{recall_row}),"")', "Média harmônica entre precisão estrita e recall estimado."])

    # Acurácia de categoria: APROVADO é correto; AJUSTADO conta como correto se categoria final = teacher original.
    # Para manter a fórmula simples, o indicador é calculado na geração do GOLD e registrado no manifest do GOLD.
    ws.append(["Cobertura completa", f'=IFERROR(SUMPRODUCT(--({sh}!${h["Status da decisão"]}$2:${h["Status da decisão"]}${end}="VALIDADO_COMPLETO"),--({sh}!${h["Recorte ausente 1"]}$2:${h["Recorte ausente 1"]}${end}=""),--({sh}!${h["Recorte ausente 2"]}$2:${h["Recorte ausente 2"]}${end}=""))/{validated},"")', "Documentos validados sem recortes adicionais humanos."])

    start = precision_row
    for r in range(start, ws.max_row + 1):
        ws.cell(r, 2).number_format = "0.0%"

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 80
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A4"


def _build_instructions(ws):
    rows = [
        ["PASSO", "O QUE FAZER"],
        ["1", "Abra 'leitura_decisoes' e leia a decisão integral pelo ID/Processo."],
        ["2", "Na aba 'revisao', confira Recorte 1/2/3. Em Validação escolha APROVADO, AJUSTADO ou REJEITADO."],
        ["3", "Se escolher AJUSTADO, edite diretamente o texto em 'Recorte N' e/ou a 'Categoria N'. O original do modelo fica preservado na aba técnica oculta."],
        ["4", "Se o modelo deixou um trecho relevante de fora, preencha 'Recorte ausente' e escolha a categoria no menu. Para mais de 2 ausências, use 'adicoes_gold'."],
        ["5", "Somente depois de ler a decisão inteira e revisar todos os recortes marque 'Status da decisão' = VALIDADO_COMPLETO."],
        ["6", "Não altere as abas técnicas ocultas. Elas guardam proveniência, texto integral e saída original para treinamento/auditoria."],
        ["GOLD", "O comando build-gold usa apenas decisões VALIDADO_COMPLETO e bloqueia documentos com candidatos ainda PENDENTE."],
    ]
    for r in rows:
        ws.append(r)
    _style_header(ws)
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 120
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(vertical="top", wrap_text=True)


def _build_lists(ws):
    ws.append(["validacao", "categoria", "status_documento"])
    max_len = max(len(CANDIDATE_STATUS), len(CATEGORIES), len(DOCUMENT_STATUS))
    for i in range(max_len):
        ws.append([
            CANDIDATE_STATUS[i] if i < len(CANDIDATE_STATUS) else "",
            CATEGORIES[i] if i < len(CATEGORIES) else "",
            DOCUMENT_STATUS[i] if i < len(DOCUMENT_STATUS) else "",
        ])


def write_review_workbook(path, decisions, candidates, prior_rows: list[dict] | None = None):
    slots = max(3, max([int(c.get("candidate_rank") or 0) for c in candidates] or [0]))
    review_rows, technical_rows = _build_review_rows(decisions, candidates, slots, prior_rows=prior_rows)

    wb = Workbook()
    review = wb.active
    review.title = "revisao"
    if review_rows:
        headers = list(review_rows[0].keys())
        review.append(headers)
        for r in review_rows:
            review.append([r.get(h, "") for h in headers])
        _format_review(review, slots, len(review_rows))

    reading = wb.create_sheet("leitura_decisoes")
    _build_reading_sheet(reading, technical_rows)

    metrics = wb.create_sheet("metricas")
    tech = wb.create_sheet("dados_tecnicos")
    _sheet(tech, technical_rows)
    tech.sheet_state = "hidden"

    cand = wb.create_sheet("candidatos_tecnicos")
    _sheet(cand, candidates)
    cand.sheet_state = "hidden"

    instr = wb.create_sheet("instrucoes")
    _build_instructions(instr)

    add = wb.create_sheet("adicoes_gold")
    add.append(["ID", "decision_sha256", "Processo", "texto_gold", "categoria_gold", "observacao", "revisor", "revisado_em"])
    _style_header(add)
    add.column_dimensions["D"].width = 80
    add.column_dimensions["E"].width = 28
    dv = DataValidation(type="list", formula1=f"=listas!$B$2:$B${len(CATEGORIES)+1}", allow_blank=True)
    add.add_data_validation(dv)
    dv.add("E2:E5000")

    listas = wb.create_sheet("listas")
    _build_lists(listas)
    listas.sheet_state = "hidden"

    _build_metrics_sheet(metrics, review, tech, slots, len(review_rows))

    wb.active = wb.sheetnames.index("revisao")
    wb.save(Path(path))


def _read_prior_review_rows(wb) -> list[dict]:
    if "revisao" in wb.sheetnames:
        return list(_rows_dict(wb["revisao"]))
    if "revisao_consolidada" in wb.sheetnames:
        return list(_rows_dict(wb["revisao_consolidada"]))
    return []


def rebuild_review(review_xlsx: str, output_xlsx: str):
    """Recria somente a planilha de revisão, sem chamar o Qwen.

    Aceita workbook v4.2/v4.3. Preserva anotações humanas já existentes quando possível.
    """
    wb = load_workbook(review_xlsx, data_only=False)
    prior = _read_prior_review_rows(wb)

    # Preferir abas técnicas originais da v4.2; na v4.3 usar as equivalentes ocultas.
    if "decisoes" in wb.sheetnames:
        decisions = list(_rows_dict(wb["decisoes"]))
    elif "dados_tecnicos" in wb.sheetnames:
        # Reconstrói formato mínimo de decisões a partir da tabela 1:1 técnica.
        decisions = []
        for t in _rows_dict(wb["dados_tecnicos"]):
            decisions.append({
                "source_row": str(t.get("source_rows") or "").split(",")[0].strip() or None,
                "processo": t.get("Processo", ""),
                "classe": t.get("classe", ""),
                "origem": t.get("origem", ""),
                "orgao_julgador": t.get("orgao_julgador", ""),
                "data": t.get("data", ""),
                "expediente": t.get("expedientes", ""),
                "prazo": t.get("prazos_origem", ""),
                "assunto": t.get("assunto", ""),
                "secao_subsecao": t.get("secao_subsecao", ""),
                "nucleo": t.get("nucleo", ""),
                "link": t.get("links_origem", ""),
                "decisao": t.get("decisao", ""),
                "rule_id": t.get("rule_id", ""),
                "rule_label": t.get("rule_label", ""),
                "route_key": t.get("route_key", ""),
                "specialist": t.get("specialist", ""),
                "teacher_status": t.get("teacher_status", ""),
                "teacher_attempts": t.get("teacher_attempts", ""),
                "teacher_response_mode": t.get("teacher_response_mode", ""),
                "decision_sha256": t.get("_decision_sha256", ""),
                "cache_hit": bool(t.get("cache_reutilizado")),
            })
    else:
        raise ValueError("Workbook não contém aba 'decisoes' nem 'dados_tecnicos'.")

    if "candidatos" in wb.sheetnames:
        candidates = list(_rows_dict(wb["candidatos"]))
    elif "candidatos_tecnicos" in wb.sheetnames:
        candidates = list(_rows_dict(wb["candidatos_tecnicos"]))
    else:
        raise ValueError("Workbook não contém aba 'candidatos' nem 'candidatos_tecnicos'.")

    # Preserva adições extras existentes e o antigo terceiro slot da v4.2.
    preserved_additions = []
    if "adicoes_gold" in wb.sheetnames:
        for a in _rows_dict(wb["adicoes_gold"]):
            text = str(a.get("texto_gold") or "").strip()
            if text:
                preserved_additions.append(dict(a))
    for r in prior:
        text = str(r.get("adicao_3_text") or "").strip()
        if text:
            preserved_additions.append({
                "decision_sha256": str(r.get("decision_sha256") or r.get("_decision_sha256") or ""),
                "Processo": r.get("Processo", ""),
                "texto_gold": text,
                "categoria_gold": str(r.get("adicao_3_category") or ""),
                "observacao": "Migrado automaticamente do 3º recorte ausente da v4.2",
                "revisor": r.get("revisor", ""),
                "revisado_em": r.get("revisado_em", ""),
            })

    write_review_workbook(output_xlsx, decisions, candidates, prior_rows=prior)

    if preserved_additions:
        out_wb = load_workbook(output_xlsx)
        add_ws = out_wb["adicoes_gold"]
        tech_ws = out_wb["dados_tecnicos"]
        tech_rows = list(_rows_dict(tech_ws))
        id_by_hash = {str(t.get("_decision_sha256") or ""): str(t.get("ID") or "") for t in tech_rows}
        for a in preserved_additions:
            h = str(a.get("decision_sha256") or "").strip()
            add_ws.append([
                id_by_hash.get(h, str(a.get("ID") or "")),
                h,
                a.get("Processo", ""),
                a.get("texto_gold", ""),
                a.get("categoria_gold", ""),
                a.get("observacao", ""),
                a.get("revisor", ""),
                a.get("revisado_em", ""),
            ])
        out_wb.save(output_xlsx)

    return {
        "input": str(review_xlsx),
        "output": str(output_xlsx),
        "decisions": len(decisions),
        "candidates": len(candidates),
        "preserved_extra_additions": len(preserved_additions),
        "qwen_rerun": False,
    }


def _tech_map(wb) -> dict[str, dict]:
    if "dados_tecnicos" not in wb.sheetnames:
        return {}
    out = {}
    for t in _rows_dict(wb["dados_tecnicos"]):
        h = str(t.get("_decision_sha256") or "")
        if h:
            out[h] = t
    return out


def _build_gold_v43(wb, output_jsonl: str):
    review = wb["revisao"]
    rows = list(_rows_dict(review))
    tech = _tech_map(wb)
    headers = [c.value for c in review[1]]
    slots = 0
    while f"Recorte {slots + 1}" in headers:
        slots += 1

    extra_additions = defaultdict(list)
    if "adicoes_gold" in wb.sheetnames:
        for a in _rows_dict(wb["adicoes_gold"]):
            text = str(a.get("texto_gold") or "").strip()
            if not text:
                continue
            h = str(a.get("decision_sha256") or "").strip()
            did = str(a.get("ID") or "").strip()
            key = h or did
            extra_additions[key].append({
                "text": text,
                "category": str(a.get("categoria_gold") or "").strip(),
                "source": "human_addition",
            })

    validated = []
    issues = []
    total_approved = total_adjusted = total_rejected = 0
    category_correct = category_total = 0

    for excel_row, r in enumerate(rows, start=2):
        if str(r.get("Status da decisão") or "").strip().upper() != "VALIDADO_COMPLETO":
            continue

        h = str(r.get("_decision_sha256") or "").strip()
        t = tech.get(h, {})
        row_issues = []
        gold = []

        for i in range(1, slots + 1):
            text = str(r.get(f"Recorte {i}") or "").strip()
            cat = str(r.get(f"Categoria {i}") or "").strip()
            status = str(r.get(f"Validação {i}") or "").strip().upper()
            teacher_text = str(t.get(f"teacher_text_{i}") or "").strip()
            teacher_cat = str(t.get(f"teacher_category_{i}") or "").strip()

            # Slot sem candidato original não exige validação.
            if not teacher_text and not text:
                continue
            if status not in {"APROVADO", "AJUSTADO", "REJEITADO"}:
                row_issues.append(f"candidato {i} ainda não revisado")
                continue
            if status == "REJEITADO":
                total_rejected += 1
                continue
            if not text:
                row_issues.append(f"candidato {i} sem texto final")
                continue
            if cat not in CATEGORIES:
                row_issues.append(f"candidato {i} com categoria inválida")
                continue

            if status == "APROVADO":
                total_approved += 1
            else:
                total_adjusted += 1
            category_total += 1
            if cat == teacher_cat:
                category_correct += 1
            gold.append({"text": text, "category": cat, "source": "candidate", "validation": status})

        for i in range(1, 3):
            text = str(r.get(f"Recorte ausente {i}") or "").strip()
            cat = str(r.get(f"Categoria ausente {i}") or "").strip()
            if not text:
                continue
            if cat not in CATEGORIES:
                row_issues.append(f"recorte ausente {i} sem categoria válida")
                continue
            gold.append({"text": text, "category": cat, "source": "human_addition"})

        did = str(r.get("ID") or "")
        for key in (h, did):
            for a in extra_additions.get(key, []):
                if a["category"] not in CATEGORIES:
                    row_issues.append("adicao_gold com categoria inválida")
                else:
                    gold.append(a)

        if row_issues:
            issues.append({"excel_row": excel_row, "ID": did, "Processo": r.get("Processo"), "issues": "; ".join(row_issues)})
            continue

        source_rows = [x.strip() for x in str(t.get("source_rows") or "").split(",") if x.strip()]
        obj = {
            "source_row": int(source_rows[0]) if source_rows and source_rows[0].isdigit() else (source_rows[0] if source_rows else None),
            "source_rows": source_rows,
            "decision_sha256": h,
            "Processo": r.get("Processo"),
            "metadata": {
                "classe": t.get("classe", r.get("Classe", "")),
                "origem": t.get("origem", ""),
                "orgao_julgador": t.get("orgao_julgador", r.get("Órgão julgador", "")),
                "data": t.get("data", ""),
                "expediente": t.get("expedientes", r.get("Expediente", "")),
                "prazo": t.get("prazos_origem", r.get("Prazo", "")),
                "assunto": t.get("assunto", r.get("Assunto", "")),
                "secao_subsecao": t.get("secao_subsecao", ""),
                "nucleo": t.get("nucleo", ""),
                "route_key": t.get("route_key", ""),
                "specialist": t.get("specialist", ""),
            },
            "decision": t.get("decisao", ""),
            "gold": gold,
        }
        validated.append(obj)

    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for obj in validated:
            f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")

    issues_path = out.with_name("gold_build_issues.csv")
    with issues_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["excel_row", "ID", "Processo", "issues"])
        writer.writeheader()
        writer.writerows(issues)

    metrics = {
        "validated_documents": len(validated),
        "blocked_documents": len(issues),
        "approved": total_approved,
        "adjusted": total_adjusted,
        "rejected": total_rejected,
        "category_accuracy_on_useful": (category_correct / category_total) if category_total else None,
        "output": str(out),
        "issues": str(issues_path),
        "source": "revisao",
    }
    return metrics


def _build_gold_legacy(wb, output_jsonl: str):
    # Compatibilidade com workbooks v4.0/v4.1/v4.2.
    if "revisao_consolidada" in wb.sheetnames:
        review = wb["revisao_consolidada"]
        rows = list(_rows_dict(review))
        headers = [c.value for c in review[1]]
        slots = 0
        while f"candidate_{slots+1}_text" in headers:
            slots += 1
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
                    gold.append({"text": text, "category": str(r.get(f"adicao_{i}_category") or "outro_acionavel"), "source": "human_addition"})
            source_rows = [x.strip() for x in str(r.get("source_rows") or "").split(",") if x.strip()]
            validated.append({
                "source_row": int(source_rows[0]) if source_rows and source_rows[0].isdigit() else None,
                "source_rows": source_rows,
                "decision_sha256": r.get("decision_sha256", ""),
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
            })
        out = Path(output_jsonl)
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as f:
            for obj in validated:
                f.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")
        return {"validated_documents": len(validated), "output": str(out), "source": "revisao_consolidada"}

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
            gold[sr].append({"text": str(a["texto_gold"]), "category": str(a.get("categoria_gold") or "outro_acionavel"), "source": "human_addition"})
    out = Path(output_jsonl)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for sr, d in dmap.items():
            f.write(json.dumps({
                "source_row": sr,
                "Processo": d.get("processo") or d.get("Processo"),
                "metadata": {k: v for k, v in d.items() if k not in {"decisao", "status_documento"}},
                "decision": d.get("decisao", ""),
                "gold": gold.get(sr, []),
            }, ensure_ascii=False, default=str) + "\n")
    return {"validated_documents": len(dmap), "output": str(out), "source": "legacy"}


def build_gold(review_xlsx: str, output_jsonl: str):
    wb = load_workbook(review_xlsx, data_only=True)
    if "revisao" in wb.sheetnames and "dados_tecnicos" in wb.sheetnames:
        return _build_gold_v43(wb, output_jsonl)
    return _build_gold_legacy(wb, output_jsonl)
