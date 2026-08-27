from __future__ import annotations

from io import BytesIO
from math import isfinite

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from code_basis import METHOD_LSM
from models import DesignResult


def _fmt(v, digits=3):
    if v is None:
        return "-"
    if isinstance(v, float):
        if not isfinite(v):
            return "N/A"
        return f"{v:.{digits}f}"
    return str(v)


def _check(result: DesignResult, name: str):
    return next((c for c in result.checks if c.name == name), None)


def _demand_capacity(check, digits=3):
    if check is None:
        return "-", "-"
    return _fmt(check.demand, digits), _fmt(check.capacity, digits)


def _table(rows, widths, header=False, font=7.2, paragraphs=False, padding=1.7):
    styles = getSampleStyleSheet()
    small = ParagraphStyle(
        name=f"tblsmall_{font}_{padding}",
        parent=styles["BodyText"],
        fontSize=font,
        leading=font + 1.25,
        spaceBefore=0,
        spaceAfter=0,
    )
    data = []
    for row in rows:
        if paragraphs:
            data.append([Paragraph(str(x), small) for x in row])
        else:
            data.append(row)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.30, colors.HexColor("#AAB2BD")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), font),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
    ]
    if header:
        commands += [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#D9E2F3")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ]
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            sval = str(val).upper()
            if sval == "SAFE":
                commands.extend([
                    ("TEXTCOLOR", (c, r), (c, r), colors.HexColor("#177245")),
                    ("FONTNAME", (c, r), (c, r), "Helvetica-Bold"),
                ])
            elif sval == "UNSAFE":
                commands.extend([
                    ("TEXTCOLOR", (c, r), (c, r), colors.HexColor("#B42318")),
                    ("FONTNAME", (c, r), (c, r), "Helvetica-Bold"),
                ])
    t.setStyle(TableStyle(commands))
    return t


def _paired_inputs(items):
    rows = [["Parameter", "Value", "Unit", "Parameter", "Value", "Unit"]]
    half = (len(items) + 1) // 2
    left = items[:half]
    right = items[half:]
    for idx in range(half):
        a = left[idx]
        b = right[idx] if idx < len(right) else ("", "", "")
        rows.append([*a, *b])
    return rows


def build_pdf(result: DesignResult, recommendation: dict | None = None) -> bytes:
    # `recommendation` is intentionally not printed. If a recommendation was applied,
    # the current result already contains the final live thicknesses to be submitted.
    _ = recommendation

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=9.5 * mm,
        leftMargin=9.5 * mm,
        topMargin=17 * mm,
        bottomMargin=11 * mm,
        allowSplitting=1,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="TitleCompact", parent=styles["Title"], alignment=TA_CENTER,
        fontSize=13.2, leading=15, spaceAfter=2.5,
    ))
    styles.add(ParagraphStyle(
        name="H1Compact", parent=styles["Heading1"], fontSize=10.2, leading=11.5,
        spaceBefore=4.2, spaceAfter=2.4, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="SmallCompact", parent=styles["BodyText"], fontSize=7.1, leading=8.5,
        spaceBefore=0, spaceAfter=1.5,
    ))
    styles.add(ParagraphStyle(
        name="TinyCompact", parent=styles["BodyText"], fontSize=6.4, leading=7.5,
        spaceBefore=0, spaceAfter=0.8,
    ))
    styles.add(ParagraphStyle(
        name="NoteCompact", parent=styles["BodyText"], fontSize=5.8, leading=6.6,
        spaceBefore=0, spaceAfter=0.35,
    ))
    styles.add(ParagraphStyle(
        name="StatusSafe", parent=styles["BodyText"], fontSize=8.5,
        textColor=colors.HexColor("#177245"), leading=10, spaceBefore=2, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="StatusUnsafe", parent=styles["BodyText"], fontSize=8.5,
        textColor=colors.HexColor("#B42318"), leading=10, spaceBefore=2, spaceAfter=2,
    ))

    i = result.inputs
    f = result.footing
    story = [
        Paragraph("SBR - WALL W1 / W1A DESIGN CALCULATION", styles["TitleCompact"]),
        Paragraph(
            f"{i.design_code} | {i.design_method} | Visible WALL W1/W1A + wall-footing scope",
            styles["SmallCompact"],
        ),
        Spacer(1, 1.5),
    ]

    story.append(Paragraph("1. Design Basis and Inputs", styles["H1Compact"]))
    input_items = [
        ("Design code", i.design_code, ""),
        ("Design method", i.design_method, ""),
        ("Concrete grade fck", _fmt(i.fck_mpa, 1), "MPa"),
        ("Steel grade fy", _fmt(i.fy_mpa, 1), "MPa"),
        ("Safe bearing capacity", _fmt(i.sbc_kn_m2, 1), "kN/m2"),
        ("Unit weight of liquid", _fmt(i.gamma_liquid_kn_m3, 1), "kN/m3"),
        ("Unit weight of RCC (locked)", _fmt(i.gamma_concrete_kn_m3, 1), "kN/m3"),
        ("Load factor (locked)", _fmt(i.load_factor, 2), "-"),
        ("Minimum stability FOS (locked)", _fmt(i.allowable_fos, 2), "-"),
        ("Crack-width selection", _fmt(i.crack_limit_mm, 2), "mm"),
        ("Wall top RL", _fmt(i.wall_top_rl_m, 3), "m"),
        ("Water top RL", _fmt(i.water_top_rl_m, 3), "m"),
        ("Raft top RL", _fmt(i.raft_top_rl_m, 3), "m"),
        ("Wall cover", _fmt(i.wall_cover_mm, 0), "mm"),
        ("Toe projection", _fmt(i.toe_projection_m, 3), "m"),
        ("Heel projection", _fmt(i.heel_projection_m, 3), "m"),
        ("Footing edge thickness", _fmt(i.footing_edge_thickness_m, 3), "m"),
        ("Footing total thickness", _fmt(i.footing_total_thickness_m, 3), "m"),
        ("Footing cover", _fmt(i.footing_cover_mm, 0), "mm"),
    ]
    story.append(_table(
        _paired_inputs(input_items),
        [43 * mm, 24 * mm, 13 * mm, 43 * mm, 24 * mm, 13 * mm],
        header=True,
        font=6.6,
        padding=1.4,
    ))

    story.append(Paragraph("2. Wall Loading / Pressure", styles["H1Compact"]))
    wall_rows = [["Station", "H", "Water h", "Pressure", "M service", "M design"]]
    for s in result.wall_stations:
        wall_rows.append([
            s.label, _fmt(s.height_m), _fmt(s.water_depth_m), _fmt(s.pressure_kn_m2),
            _fmt(s.service_moment_knm_m), _fmt(s.factored_moment_knm_m),
        ])
    story.append(_table(
        wall_rows,
        [22 * mm, 24 * mm, 27 * mm, 29 * mm, 34 * mm, 34 * mm],
        header=True,
        font=6.3,
        padding=1.25,
    ))

    story.append(Paragraph("3. Wall Section / Reinforcement Design", styles["H1Compact"]))
    wr = [["Station", "t req", "t prov", "d", "Ast req", "Ast prov", "Vert.", "Horiz."]]
    for s in result.wall_stations:
        wr.append([
            s.label, _fmt(s.required_thickness_mm, 1), _fmt(s.provided_thickness_mm, 0),
            _fmt(s.effective_depth_mm, 0), _fmt(s.ast_required_mm2_m, 1),
            _fmt(s.ast_provided_mm2_m, 1), s.vertical_status, s.horizontal_status,
        ])
    story.append(_table(
        wr,
        [19 * mm, 20 * mm, 20 * mm, 17 * mm, 27 * mm, 27 * mm, 20 * mm, 20 * mm],
        header=True,
        font=6.2,
        padding=1.2,
    ))

    story.append(Paragraph("4. Wall Serviceability", styles["H1Compact"]))
    wall_shear = _check(result, "Wall shear")
    shear_d, shear_c = _demand_capacity(wall_shear, 4)
    if i.design_method == METHOD_LSM:
        c_stress = _check(result, "Wall crack check - concrete stress")
        s_stress = _check(result, "Wall crack check - steel stress")
        crack_chk = _check(result, "Wall crack width")
        cd, cc = _demand_capacity(c_stress, 3)
        sd, sc = _demand_capacity(s_stress, 3)
        wd, wc_cap = _demand_capacity(crack_chk, 2)
        service_rows = [
            ["Check", "Demand", "Allowable / capacity"],
            ["Wall shear stress (N/mm2)", shear_d, shear_c],
            ["Wall steel stress (N/mm2)", sd, sc],
            ["Wall concrete compression (N/mm2)", cd, cc],
            ["Wall crack width (mm)", wd, wc_cap],
        ]
    else:
        t_chk = _check(result, "Wall cracking resistance - concrete bending tension")
        s_chk = _check(result, "Wall WSM steel stress")
        c_chk = _check(result, "Wall WSM concrete compression")
        td, tc = _demand_capacity(t_chk, 3)
        sd, sc = _demand_capacity(s_chk, 3)
        cd, cc = _demand_capacity(c_chk, 3)
        service_rows = [
            ["Working-stress check", "Demand", "Permissible"],
            ["Wall shear stress (N/mm2)", shear_d, shear_c],
            ["Concrete bending tension (N/mm2)", td, tc],
            ["Steel tensile stress (N/mm2)", sd, sc],
            ["Concrete compression (N/mm2)", cd, cc],
            ["Crack-width selection", _fmt(i.crack_limit_mm, 2), "Not governing in WSM"],
        ]
    story.append(_table(service_rows, [91 * mm, 42 * mm, 47 * mm], header=True, font=6.7, padding=1.35))

    story.append(Paragraph("5. Wall Footing - Stability", styles["H1Compact"]))
    stability_rows = [
        ["Parameter", "Result", "Limit"],
        ["Toe / heel projection (m)", f"{_fmt(f['toe_projection_m'])} / {_fmt(f['heel_projection_m'])}", "-"],
        ["Base width (m)", _fmt(f["base_width_m"]), "-"],
        ["Overturning moment (kNm)", _fmt(f["overturning_moment_knm"]), "-"],
        ["Gross stabilising moment (kNm)", _fmt(f["gross_stabilising_moment_knm"]), "-"],
        ["FOS", _fmt(f["fos"], 4), _fmt(i.allowable_fos, 2)],
        ["|e| (m)", _fmt(f["eccentricity_abs_m"], 4), _fmt(f["eccentricity_allow_m"], 4)],
        ["pmax (kN/m2)", _fmt(f["pmax_kn_m2"]), _fmt(i.sbc_kn_m2, 1)],
        ["pmin (kN/m2)", _fmt(f["pmin_kn_m2"]), ">= 0"],
    ]
    footing_design_rows = [
        ["Parameter", "Value", "Unit"],
        ["Heel net moment", _fmt(f["heel_moment_knm_m"]), "kNm/m"],
        ["Toe net moment", _fmt(f["toe_moment_knm_m"]), "kNm/m"],
        ["Governing design moment", _fmt(f["governing_factored_moment_knm_m"]), "kNm/m"],
        ["Required / provided thickness", f"{_fmt(f['required_thickness_mm'], 1)} / {_fmt(f['provided_thickness_mm'], 1)}", "mm"],
        ["Top d / bottom d", f"{f['top_effective_depth_mm']:.1f} / {f['bottom_effective_depth_mm']:.1f}", "mm"],
        ["Top Ast req / prov", f"{_fmt(f['top_ast_required_mm2_m'], 1)} / {_fmt(f['top_ast_provided_mm2_m'], 1)}", "mm2/m"],
        ["Bottom Ast req / prov", f"{_fmt(f['bottom_ast_required_mm2_m'], 1)} / {_fmt(f['bottom_ast_provided_mm2_m'], 1)}", "mm2/m"],
        ["Heel tau_v / tau_c", f"{f['heel_tau_v_mpa']:.4f} / {f['heel_tau_c_mpa']:.4f}", "N/mm2"],
        ["Toe tau_v / tau_c", f"{f['toe_tau_v_mpa']:.4f} / {f['toe_tau_c_mpa']:.4f}", "N/mm2"],
        [
            "Footing serviceability",
            _fmt(f["crack"].get("wcr_mm"), 2) if f["crack"].get("wcr_mm") is not None else "WSM stress control",
            "mm" if f["crack"].get("wcr_mm") is not None else "",
        ],
    ]
    stab_table = _table(stability_rows, [47 * mm, 24 * mm, 18 * mm], header=True, font=6.35, padding=1.25)
    foot_table = _table(footing_design_rows, [46 * mm, 35 * mm, 16 * mm], header=True, font=6.2, padding=1.15)
    pair = Table([[stab_table, foot_table]], colWidths=[91 * mm, 99 * mm], hAlign="LEFT")
    pair.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 1)]))
    story.append(pair)

    story.append(Paragraph("6. Check Summary", styles["H1Compact"]))
    vertical_rows = [["Station", "Required", "Provided", "Status"]]
    horizontal_rows = [["Station", "Required", "Main prov.", "Total + corner", "Status"]]
    for s in result.wall_stations:
        vertical_rows.append([
            s.label, _fmt(s.ast_required_mm2_m, 0), _fmt(s.ast_provided_mm2_m, 0), s.vertical_status,
        ])
        horizontal_rows.append([
            s.label, _fmt(s.horizontal_required_mm2_m, 0), _fmt(s.horizontal_main_provided_mm2_m, 0),
            _fmt(s.horizontal_total_provided_mm2_m, 0), s.horizontal_status,
        ])
    v_title = Paragraph("<b>Vertical Reinforcement (mm2/m)</b>", styles["TinyCompact"])
    h_title = Paragraph("<b>Horizontal Reinforcement (mm2/m)</b>", styles["TinyCompact"])
    v_table = _table(vertical_rows, [18 * mm, 22 * mm, 22 * mm, 18 * mm], header=True, font=5.9, padding=1.0)
    h_table = _table(horizontal_rows, [17 * mm, 18 * mm, 18 * mm, 22 * mm, 17 * mm], header=True, font=5.7, padding=0.9)
    reinf_pair = Table([[v_title, h_title], [v_table, h_table]], colWidths=[84 * mm, 98 * mm], hAlign="LEFT")
    reinf_pair.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    story.append(reinf_pair)

    general_checks = [
        c for c in result.checks
        if not c.name.startswith("Wall vertical design -")
        and not c.name.startswith("Wall horizontal steel -")
    ]
    check_rows = [["Check", "Status", "Demand", "Capacity", "Unit"]]
    for c in general_checks:
        check_rows.append([c.name, c.status, _fmt(c.demand, 3), _fmt(c.capacity, 3), c.unit])
    story.append(Spacer(1, 1.5))
    story.append(_table(check_rows, [86 * mm, 20 * mm, 29 * mm, 29 * mm, 20 * mm], header=True, font=5.9, paragraphs=True, padding=1.0))
    status_style = styles["StatusSafe"] if result.overall_status == "SAFE" else styles["StatusUnsafe"]
    status_text = (
        "SAFE for all checks currently implemented in this application."
        if result.overall_status == "SAFE"
        else "UNSAFE - one or more implemented mandatory checks fail."
    )
    story.append(Paragraph(f"<b>Overall status: {status_text}</b>", status_style))

    story.append(Paragraph("7. Warnings and Limitations", styles["H1Compact"]))
    if result.warnings:
        for w in result.warnings:
            story.append(Paragraph(f"- {w}", styles["NoteCompact"]))
    else:
        story.append(Paragraph("- None.", styles["NoteCompact"]))

    story.append(Paragraph("8. Approved Source Reconciliation", styles["H1Compact"]))
    for n in result.reconciliation_notes:
        story.append(Paragraph(f"- {n}", styles["NoteCompact"]))

    story.append(Paragraph("9. Calculation Formula Trace", styles["H1Compact"]))
    trace_rows = [["Calculation", "Formula / numerical substitution", "Result", "Source"]]
    for t in result.formula_trace:
        trace_rows.append([t.calculation, f"{t.formula}<br/>{t.substitution}", t.result, t.source])
    story.append(_table(
        trace_rows,
        [38 * mm, 82 * mm, 30 * mm, 34 * mm],
        header=True,
        font=5.8,
        paragraphs=True,
        padding=1.0,
    ))

    p = i.project

    def header_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#B8BEC6"))
        canvas.setLineWidth(0.35)
        canvas.setFillColor(colors.HexColor("#4B5563"))
        canvas.setFont("Helvetica", 6.2)

        project = p.project.strip() or "-"
        structure = p.structure.strip() or "SBR - WALL W1 / W1A"
        doc_no = p.document_no.strip() or "-"
        revision = p.revision.strip() or "-"
        header_1 = f"Project: {project} | Structure: {structure}"
        header_2 = f"Document: {doc_no} | Revision: {revision}"
        canvas.drawString(9.5 * mm, A4[1] - 6.4 * mm, header_1[:125])
        canvas.drawString(9.5 * mm, A4[1] - 9.3 * mm, header_2[:125])
        canvas.line(9.5 * mm, A4[1] - 11.0 * mm, A4[0] - 9.5 * mm, A4[1] - 11.0 * mm)

        prepared = p.prepared_by.strip() or "-"
        checked = p.checked_by.strip() or "-"
        canvas.line(9.5 * mm, 8.5 * mm, A4[0] - 9.5 * mm, 8.5 * mm)
        canvas.drawString(9.5 * mm, 5.5 * mm, f"Prepared: {prepared} | Checked: {checked}")
        canvas.drawRightString(A4[0] - 9.5 * mm, 5.5 * mm, f"Page {doc_obj.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return buf.getvalue()
