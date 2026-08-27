from __future__ import annotations

from io import BytesIO
from math import isfinite
import xlsxwriter
from models import DesignResult


def _safe(v):
    if isinstance(v, float) and not isfinite(v):
        return "N/A - thickness/stress governs"
    return v


def build_excel(result: DesignResult, recommendation: dict | None = None) -> bytes:
    out = BytesIO()
    wb = xlsxwriter.Workbook(out, {"in_memory": True})
    fmt_title = wb.add_format({"bold": True, "font_size": 16, "align": "center", "valign": "vcenter", "bg_color": "#1F4E78", "font_color": "white"})
    fmt_h = wb.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
    fmt = wb.add_format({"border": 1})
    fmt_num = wb.add_format({"border": 1, "num_format": "0.000"})
    fmt_safe = wb.add_format({"border": 1, "font_color": "#177245", "bold": True})
    fmt_unsafe = wb.add_format({"border": 1, "font_color": "#B42318", "bold": True})

    def setup(ws):
        ws.set_paper(9)  # A4
        ws.fit_to_pages(1, 0)
        ws.set_margins(0.35,0.35,0.5,0.5)
        ws.set_landscape()
        ws.repeat_rows(0, 0)

    # Summary
    ws = wb.add_worksheet("Summary"); setup(ws)
    ws.merge_range("A1:F2", "SBR - WALL W1 / W1A DESIGN CALCULATION", fmt_title)
    ws.write_row("A4", ["Overall Status", result.overall_status, "Wall", result.wall_status, "Footing", result.footing_status], fmt_h)
    ws.write("A6", "Design code", fmt_h); ws.write("B6", result.inputs.design_code, fmt)
    ws.write("C6", "Design method", fmt_h); ws.merge_range("D6:F6", result.inputs.design_method, fmt)
    ws.write("A7", "Important scope note", fmt_h); ws.merge_range("B7:F7", "Visible workbook scope only; hidden areas are reference-only where needed for visible dependencies.", fmt)
    ws.set_column("A:A", 32); ws.set_column("B:F", 22)

    # Inputs
    ws = wb.add_worksheet("Inputs"); setup(ws)
    ws.write_row(0,0,["Parameter","Value","Unit"],fmt_h)
    i=result.inputs
    rows=[
        ("Design code",i.design_code,""),("Design method",i.design_method,""),
        ("fck",i.fck_mpa,"MPa"),("fy",i.fy_mpa,"MPa"),("SBC",i.sbc_kn_m2,"kN/m2"),("Unit wt liquid",i.gamma_liquid_kn_m3,"kN/m3"),
        ("Unit wt concrete (locked)",i.gamma_concrete_kn_m3,"kN/m3"),("Load factor (locked)",i.load_factor,""),("Minimum stability FOS (locked)",i.allowable_fos,""),
        ("Crack limit",i.crack_limit_mm,"mm"),("Wall top RL",i.wall_top_rl_m,"m"),
        ("Water top RL",i.water_top_rl_m,"m"),("Raft top RL",i.raft_top_rl_m,"m"),("Wall cover",i.wall_cover_mm,"mm"),
        ("Toe projection",i.toe_projection_m,"m"),("Heel projection",i.heel_projection_m,"m"),("Footing edge thickness",i.footing_edge_thickness_m,"m"),
        ("Footing total thickness",i.footing_total_thickness_m,"m"),("Footing cover",i.footing_cover_mm,"mm"),
    ]
    for r,row in enumerate(rows,1): ws.write_row(r,0,row,fmt)
    ws.set_column("A:A",35); ws.set_column("B:C",18)

    # Wall
    ws = wb.add_worksheet("Wall Design"); setup(ws)
    headers=["Station","Height m","Water h m","Pressure kN/m2","M service","M factored","t req mm","t prov mm","d mm","Ast req","Ast prov","Vert status","Horiz req","Horiz main","Horiz total","Horiz status"]
    ws.write_row(0,0,headers,fmt_h)
    for r,s in enumerate(result.wall_stations,1):
        vals=[s.label,s.height_m,s.water_depth_m,s.pressure_kn_m2,s.service_moment_knm_m,s.factored_moment_knm_m,s.required_thickness_mm,s.provided_thickness_mm,s.effective_depth_mm,s.ast_required_mm2_m,s.ast_provided_mm2_m,s.vertical_status,s.horizontal_required_mm2_m,s.horizontal_main_provided_mm2_m,s.horizontal_total_provided_mm2_m,s.horizontal_status]
        for c,v in enumerate(vals):
            f=fmt_safe if v=="SAFE" else fmt_unsafe if v=="UNSAFE" else fmt_num if isinstance(v,(int,float)) else fmt
            ws.write(r,c,_safe(v),f)
    ws.set_column(0,0,12); ws.set_column(1,15,14)

    # Footing
    ws=wb.add_worksheet("Footing"); setup(ws)
    ws.write_row(0,0,["Parameter","Value","Unit"],fmt_h)
    f=result.footing
    foot_rows=[
        ("Toe projection",f["toe_projection_m"],"m"),("Heel projection",f["heel_projection_m"],"m"),("Base width",f["base_width_m"],"m"),
        ("Overturning moment",f["overturning_moment_knm"],"kNm"),("Gross stabilising moment",f["gross_stabilising_moment_knm"],"kNm"),
        ("FOS",f["fos"],""),("Eccentricity abs",f["eccentricity_abs_m"],"m"),("pmax",f["pmax_kn_m2"],"kN/m2"),("pmin",f["pmin_kn_m2"],"kN/m2"),
        ("Heel moment",f["heel_moment_knm_m"],"kNm/m"),("Toe moment",f["toe_moment_knm_m"],"kNm/m"),("Governing factored moment",f["governing_factored_moment_knm_m"],"kNm/m"),
        ("Required thickness",f["required_thickness_mm"],"mm"),("Provided thickness",f["provided_thickness_mm"],"mm"),
        ("Top Ast req",f["top_ast_required_mm2_m"],"mm2/m"),("Top Ast prov",f["top_ast_provided_mm2_m"],"mm2/m"),
        ("Bottom Ast req",f["bottom_ast_required_mm2_m"],"mm2/m"),("Bottom Ast prov",f["bottom_ast_provided_mm2_m"],"mm2/m"),
        ("Heel tau_v",f["heel_tau_v_mpa"],"N/mm2"),("Heel tau_c",f["heel_tau_c_mpa"],"N/mm2"),("Toe tau_v",f["toe_tau_v_mpa"],"N/mm2"),("Toe tau_c",f["toe_tau_c_mpa"],"N/mm2"),
        ("Footing serviceability", f["crack"].get("wcr_mm") if f["crack"].get("wcr_mm") is not None else "N/A - WSM stress control", "mm" if f["crack"].get("wcr_mm") is not None else ""),
    ]
    for r,row in enumerate(foot_rows,1): ws.write_row(r,0,[_safe(v) for v in row],fmt)
    ws.set_column("A:A",35); ws.set_column("B:C",18)

    # Checks
    ws=wb.add_worksheet("Checks"); setup(ws)
    ws.write_row(0,0,["Check","Status","Demand","Capacity","Unit","Note"],fmt_h)
    for r,c in enumerate(result.checks,1):
        ws.write(r,0,c.name,fmt); ws.write(r,1,c.status,fmt_safe if c.status=="SAFE" else fmt_unsafe if c.status=="UNSAFE" else fmt)
        demand = _safe(c.demand); capacity = _safe(c.capacity)
        ws.write(r,2,demand,fmt_num if isinstance(demand,(int,float)) else fmt); ws.write(r,3,capacity,fmt_num if isinstance(capacity,(int,float)) else fmt); ws.write(r,4,c.unit,fmt); ws.write(r,5,c.note,fmt)
    ws.set_column("A:A",45); ws.set_column("B:E",16); ws.set_column("F:F",55)

    # Formula Trace
    ws=wb.add_worksheet("Formula Trace"); setup(ws)
    ws.write_row(0,0,["Calculation","Formula","Numerical substitution","Result","Source"],fmt_h)
    for r,t in enumerate(result.formula_trace,1): ws.write_row(r,0,[t.calculation,t.formula,t.substitution,t.result,t.source],fmt)
    ws.set_column("A:A",28); ws.set_column("B:C",55); ws.set_column("D:D",25); ws.set_column("E:E",35)

    # Reconciliation
    ws=wb.add_worksheet("Reconciliation"); setup(ws)
    ws.write_row(0,0,["Approved / implemented reconciliation note"],fmt_h)
    for r,n in enumerate(result.reconciliation_notes,1): ws.write(r,0,n,fmt)
    ws.set_column("A:A",120)
    if recommendation:
        ws.write(len(result.reconciliation_notes)+3,0,"Thickness-only recommendation",fmt_h)
        ws.write(len(result.reconciliation_notes)+4,0,str(recommendation),fmt)

    wb.close(); out.seek(0); return out.getvalue()
