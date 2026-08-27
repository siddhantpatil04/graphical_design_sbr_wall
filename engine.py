from __future__ import annotations

from copy import deepcopy
from math import floor, sqrt
from typing import Iterable

from models import (
    CheckResult,
    DesignInputs,
    DesignResult,
    FormulaTrace,
    RebarLayer,
    WallStationInput,
    WallStationResult,
)
from tables import shear_strength_tau_c
from source_map import CORRECTION_NOTES
from code_basis import (
    CODE_1965,
    CODE_2009,
    CODE_2021,
    METHOD_LSM,
    METHOD_WSM,
    normalise_method,
    profile,
    permissible_bending_tension,
    permissible_concrete_bending_compression,
    permissible_steel_tension_wsm,
    modular_ratio_wsm,
    wall_min_ratio_per_face,
    footing_min_ratio_per_face,
    shear_strength_wsm_1965,
    shear_strength_wsm_2009,
)


def default_wall_stations() -> list[WallStationInput]:
    labels = ["0%", "10%", "20%", "30%", "40%", "50%", "60%", "70%", "Cut-off", "80%", "90%", "100%"]
    fracs = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, None, 0.8, 0.9, 1.0]
    thk = [200, 200, 200, 200, 200, 200, 200, 225, 240, 293, 347, 400]
    vmain = [(8, 125)] * 12
    vextra = [(0, 125)] * 7 + [(16, 125)] * 5
    hmain = [(8, 125)] * 5 + [(8, 130)] * 2 + [(12, 150)] * 5
    hcorner = [(8, 250)] * 5 + [(8, 260)] * 2 + [(10, 300)] * 5
    return [
        WallStationInput(
            label=labels[i], fraction=fracs[i], provided_thickness_mm=float(thk[i]),
            vertical_main=RebarLayer(*vmain[i]), vertical_extra=RebarLayer(*vextra[i]),
            horizontal_main=RebarLayer(*hmain[i]), horizontal_corner=RebarLayer(*hcorner[i]),
            special_height_m=4.5 if fracs[i] is None else None,
        )
        for i in range(12)
    ]


def default_inputs() -> DesignInputs:
    d = DesignInputs()
    d.wall_stations = default_wall_stations()
    return d


def _bar_area(layers: Iterable[RebarLayer]) -> float:
    return sum(layer.area_per_m() for layer in layers)


def _max_dia(layers: Iterable[RebarLayer]) -> float:
    vals = [layer.dia_mm for layer in layers if layer.dia_mm > 0 and layer.spacing_mm > 0]
    return max(vals) if vals else 0.0


def _rounddown_2(x: float) -> float:
    return floor(max(x, 0.0) * 100.0 + 1e-12) / 100.0


def _bm_coefficient(fck: float) -> float:
    # Corrected supplied-workbook LSM basis.
    return 0.13272586446540546 * fck


def _flexural_ast(mu_knm_m: float, fck: float, fy: float, d_mm: float) -> tuple[float, bool]:
    if mu_knm_m <= 0:
        return 0.0, True
    if fck <= 0 or fy <= 0 or d_mm <= 0:
        return float("inf"), False
    rad = 1.0 - (4.6 * mu_knm_m * 1e6) / (fck * 1000.0 * d_mm**2)
    if rad < 0:
        return float("inf"), False
    ast = abs((0.5 * fck / fy) * (1.0 - sqrt(rad)) * 1000.0 * d_mm)
    return ast, True


def _required_depth(mu_knm_m: float, q: float) -> float:
    if mu_knm_m <= 0:
        return 0.0
    if q <= 0:
        return float("inf")
    return sqrt(abs(mu_knm_m) * 1000.0 / q)


def _crack_width(
    *, service_m_knm_m: float, as_mm2_m: float, b_mm: float, h_mm: float,
    cover_mm: float, d_mm: float, fck: float, fy: float, bar_dia_mm: float,
    effective_spacing_mm: float,
) -> dict[str, float | str | bool | None]:
    if service_m_knm_m <= 0:
        return {"applicable": False, "wcr_mm": 0.0, "fs_mpa": 0.0, "fcb_mpa": 0.0,
                "x_mm": 0.0, "z_mm": 0.0, "eps1": 0.0, "eps2": 0.0, "eps_m": 0.0, "acr_mm": 0.0}
    if min(as_mm2_m, b_mm, h_mm, d_mm, fck, fy) <= 0:
        raise ValueError("Invalid input in crack-width calculation.")
    rho = as_mm2_m / (b_mm * d_mm)
    alpha_e = (200.0 * 1e3) / (0.5 * 5000.0 * sqrt(fck))
    a = alpha_e * rho
    if a <= 0:
        raise ValueError("Invalid transformed reinforcement ratio in crack-width calculation.")
    x_over_d = a * (sqrt(1.0 + 2.0 / a) - 1.0)
    x_mm = x_over_d * d_mm
    z_mm = d_mm - x_mm / 3.0
    if z_mm <= 0 or d_mm <= x_mm:
        raise ValueError("Invalid neutral-axis/lever-arm result in crack-width calculation.")
    fs = service_m_knm_m * 1e6 / (z_mm * as_mm2_m)
    fcb = 2.0 * service_m_knm_m * 1e6 / (z_mm * x_mm * b_mm)
    es = 200.0 * 1e3
    eps1 = ((h_mm - x_mm) / (d_mm - x_mm)) * (fs / es)
    eps2 = (b_mm * (h_mm - x_mm)**2) / (3.0 * es * as_mm2_m * (d_mm - x_mm))
    eps_m = eps1 - eps2
    acr = sqrt((effective_spacing_mm / 2.0)**2 + (cover_mm + bar_dia_mm / 2.0)**2) - bar_dia_mm / 2.0
    denom = 1.0 + 2.0 * (acr - cover_mm) / (h_mm - x_mm)
    raw_wcr = 3.0 * acr * eps_m / denom
    return {
        "applicable": True, "rho": rho, "alpha_e": alpha_e, "x_mm": x_mm, "z_mm": z_mm,
        "fs_mpa": fs, "fcb_mpa": fcb, "eps1": eps1, "eps2": eps2, "eps_m": eps_m,
        "acr_mm": acr, "wcr_raw_mm": raw_wcr, "wcr_mm": _rounddown_2(raw_wcr),
    }


def _wsm_uncracked_stress(
    *, service_m_knm_m: float, h_mm: float, cover_mm: float, fck: float,
    tension_as_mm2: float, tension_dia_mm: float, compression_as_mm2: float,
    compression_dia_mm: float, b_mm: float = 1000.0,
) -> dict[str, float]:
    if service_m_knm_m <= 0:
        return {"sigma_t_mpa": 0.0, "sigma_c_mpa": 0.0, "steel_tension_mpa": 0.0,
                "ybar_mm": h_mm/2.0, "I_mm4": b_mm*h_mm**3/12.0, "m": modular_ratio_wsm(fck)}
    m = modular_ratio_wsm(fck)
    ac = b_mm * h_mm
    yc = h_mm / 2.0
    y_t = h_mm - cover_mm - tension_dia_mm / 2.0
    y_c = cover_mm + compression_dia_mm / 2.0 if compression_as_mm2 > 0 else yc
    if y_t <= 0 or y_t >= h_mm:
        raise ValueError("Invalid WSM tension-steel location.")
    at = (m - 1.0) * max(tension_as_mm2, 0.0)
    acs = (m - 1.0) * max(compression_as_mm2, 0.0)
    area = ac + at + acs
    ybar = (ac * yc + at * y_t + acs * y_c) / area
    I = b_mm*h_mm**3/12.0 + ac*(yc-ybar)**2 + at*(y_t-ybar)**2 + acs*(y_c-ybar)**2
    M = service_m_knm_m * 1e6
    sigma_t = M * max(h_mm-ybar, ybar) / I
    sigma_c = M * min(h_mm-ybar, ybar) / I
    steel_t = m * M * abs(y_t-ybar) / I
    return {"sigma_t_mpa": sigma_t, "sigma_c_mpa": sigma_c, "steel_tension_mpa": steel_t,
            "ybar_mm": ybar, "I_mm4": I, "m": m}


def _wsm_cracked_stresses(service_m_knm_m: float, as_mm2: float, d_mm: float, fck: float, b_mm: float = 1000.0) -> dict[str, float]:
    if service_m_knm_m <= 0:
        return {"fs_mpa": 0.0, "fcb_mpa": 0.0, "x_mm": 0.0, "z_mm": d_mm}
    if as_mm2 <= 0 or d_mm <= 0:
        return {"fs_mpa": float("inf"), "fcb_mpa": float("inf"), "x_mm": 0.0, "z_mm": 0.0}
    m = modular_ratio_wsm(fck)
    a = m * as_mm2 / (b_mm * d_mm)
    x_over_d = a * (sqrt(1.0 + 2.0 / a) - 1.0)
    x = x_over_d * d_mm
    z = d_mm - x/3.0
    if z <= 0 or x <= 0:
        return {"fs_mpa": float("inf"), "fcb_mpa": float("inf"), "x_mm": x, "z_mm": z}
    M = service_m_knm_m * 1e6
    return {
        "fs_mpa": M/(as_mm2*z),
        "fcb_mpa": 2.0*M/(b_mm*x*z),
        "x_mm": x,
        "z_mm": z,
    }


def _wsm_required_ast(
    *, service_m_knm_m: float, h_mm: float, d_mm: float, cover_mm: float, fck: float,
    tension_dia_mm: float, compression_as_mm2: float, compression_dia_mm: float,
    sigma_t_allow: float, sigma_s_allow: float, sigma_c_allow: float,
) -> float:
    if service_m_knm_m <= 0:
        return 0.0

    def passes(as_t: float) -> bool:
        unc = _wsm_uncracked_stress(
            service_m_knm_m=service_m_knm_m, h_mm=h_mm, cover_mm=cover_mm, fck=fck,
            tension_as_mm2=as_t, tension_dia_mm=tension_dia_mm,
            compression_as_mm2=compression_as_mm2, compression_dia_mm=compression_dia_mm,
        )
        cr = _wsm_cracked_stresses(service_m_knm_m, as_t, d_mm, fck)
        return unc["sigma_t_mpa"] <= sigma_t_allow and cr["fs_mpa"] <= sigma_s_allow and cr["fcb_mpa"] <= sigma_c_allow

    lo, hi = 1.0, 20000.0
    if not passes(hi):
        return float("inf")
    for _ in range(80):
        mid = (lo + hi)/2.0
        if passes(mid):
            hi = mid
        else:
            lo = mid
    return hi


def _wsm_required_thickness(
    *, service_m_knm_m: float, cover_mm: float, fck: float, tension_as_mm2: float,
    tension_dia_mm: float, compression_as_mm2: float, compression_dia_mm: float,
    sigma_t_allow: float, sigma_s_allow: float, sigma_c_allow: float,
) -> float:
    if service_m_knm_m <= 0:
        return 0.0
    min_h = max(75.0, cover_mm + max(tension_dia_mm, compression_dia_mm)/2.0 + 25.0)

    def passes(h: float) -> bool:
        d = h - cover_mm - tension_dia_mm/2.0
        if d <= 0:
            return False
        unc = _wsm_uncracked_stress(
            service_m_knm_m=service_m_knm_m, h_mm=h, cover_mm=cover_mm, fck=fck,
            tension_as_mm2=tension_as_mm2, tension_dia_mm=tension_dia_mm,
            compression_as_mm2=compression_as_mm2, compression_dia_mm=compression_dia_mm,
        )
        cr = _wsm_cracked_stresses(service_m_knm_m, tension_as_mm2, d, fck)
        return unc["sigma_t_mpa"] <= sigma_t_allow and cr["fs_mpa"] <= sigma_s_allow and cr["fcb_mpa"] <= sigma_c_allow

    lo, hi = min_h, 2000.0
    if not passes(hi):
        return float("inf")
    for _ in range(80):
        mid = (lo + hi)/2.0
        if passes(mid):
            hi = mid
        else:
            lo = mid
    return hi


def validate_inputs(inp: DesignInputs) -> list[str]:
    errors: list[str] = []
    try:
        method = normalise_method(inp.design_code, inp.design_method)
    except ValueError as exc:
        return [str(exc)]
    positive_fields = {
        "fck": inp.fck_mpa, "fy": inp.fy_mpa, "SBC": inp.sbc_kn_m2,
        "liquid unit weight": inp.gamma_liquid_kn_m3, "concrete unit weight": inp.gamma_concrete_kn_m3,
        "wall cover": inp.wall_cover_mm, "footing cover": inp.footing_cover_mm,
        "toe projection": inp.toe_projection_m, "heel projection": inp.heel_projection_m,
        "footing edge thickness": inp.footing_edge_thickness_m,
        "footing total thickness": inp.footing_total_thickness_m,
    }
    for name, val in positive_fields.items():
        if val <= 0:
            errors.append(f"{name} must be greater than zero.")
    if inp.wall_top_rl_m <= inp.raft_top_rl_m:
        errors.append("Wall top RL must be above raft top RL.")
    if inp.water_top_rl_m > inp.wall_top_rl_m:
        errors.append("Water top RL cannot exceed wall top RL for this calculation scope.")
    if inp.footing_total_thickness_m < inp.footing_edge_thickness_m:
        errors.append("Total footing thickness must be at least the edge thickness.")
    if inp.wall_taper_height_m < 0:
        errors.append("Wall taper height cannot be negative.")
    if not inp.wall_stations:
        errors.append("Wall station schedule is empty.")
    for s in inp.wall_stations:
        if s.provided_thickness_mm <= inp.wall_cover_mm:
            errors.append(f"{s.label}: provided wall thickness is not greater than cover.")
    if method == METHOD_LSM and inp.crack_limit_mm > 0.20 + 1e-9:
        errors.append("The implemented IS 3370 limit-state branches do not permit a crack-width limit above 0.20 mm.")
    if inp.design_code == CODE_1965 and inp.fck_mpa < 15:
        errors.append("IS 3370:1965 concrete cracking table is not implemented below M15.")
    if inp.design_code == CODE_2009 and inp.fck_mpa < 25:
        errors.append("IS 3370:2009 Part 2 Table 1 starts at M25 for the implemented reinforced-concrete branch.")
    return errors


def calculate(inputs: DesignInputs) -> DesignResult:
    inp = deepcopy(inputs)
    inp.design_method = normalise_method(inp.design_code, inp.design_method)
    errors = validate_inputs(inp)
    if errors:
        raise ValueError("; ".join(errors))

    prof = profile(inp.design_code, inp.design_method)
    is_lsm = inp.design_method == METHOD_LSM
    design_factor = inp.load_factor if is_lsm else 1.0
    traces: list[FormulaTrace] = []
    checks: list[CheckResult] = []
    warnings: list[str] = list(prof.notes)

    wall_top_thk_m = inp.wall_stations[0].provided_thickness_mm / 1000.0
    wall_base_thk_m = inp.wall_stations[-1].provided_thickness_mm / 1000.0
    footing_haunch_m = inp.footing_total_thickness_m - inp.footing_edge_thickness_m
    side_wall_bottom_rl = inp.raft_top_rl_m + footing_haunch_m
    liquid_depth = max(0.0, inp.water_top_rl_m - side_wall_bottom_rl + inp.freeboard_m)
    total_wall_depth = inp.wall_top_rl_m - side_wall_bottom_rl
    dry_height = inp.wall_top_rl_m - inp.water_top_rl_m
    q = _bm_coefficient(inp.fck_mpa) if is_lsm else None

    traces.extend([
        FormulaTrace("Design standard", "Selected code / method", f"{inp.design_code} / {inp.design_method}", f"{inp.design_code} — {inp.design_method}", "Code selector"),
        FormulaTrace("Unit weight of RCC (locked)", "Approved fixed design parameter", f"gamma_c = {inp.gamma_concrete_kn_m3:.2f}", f"{inp.gamma_concrete_kn_m3:.2f} kN/m3", "Locked UI parameter / workbook basis"),
        FormulaTrace("Load factor (locked)", "gamma_f = approved fixed value for LSM; WSM uses service factor 1.0", f"stored={inp.load_factor:.2f}; effective={design_factor:.2f}", f"{design_factor:.2f}", "Locked UI parameter / selected design method"),
        FormulaTrace("Minimum stability FOS (locked)", "FOS_required = approved fixed value", f"FOS_required = {inp.allowable_fos:.2f}", f"{inp.allowable_fos:.2f}", "Locked UI parameter / workbook basis"),
        FormulaTrace("Selected crack-width limit", "w_limit = user-selected dropdown value", f"w_limit = {inp.crack_limit_mm:.2f} mm", f"{inp.crack_limit_mm:.2f} mm" if is_lsm else "Stored only - WSM uses stress-control acceptance", "Web-app design input"),
        FormulaTrace("Side-wall bottom RL", "RLbottom = RLraft + (tfoot,total - tfoot,edge)",
                     f"{inp.raft_top_rl_m:.3f} + ({inp.footing_total_thickness_m:.3f} - {inp.footing_edge_thickness_m:.3f})",
                     f"{side_wall_bottom_rl:.3f} m", "WALL W1!H162"),
        FormulaTrace("Liquid depth", "h = RLwater - RLbottom + freeboard",
                     f"{inp.water_top_rl_m:.3f} - {side_wall_bottom_rl:.3f} + {inp.freeboard_m:.3f}",
                     f"{liquid_depth:.3f} m", "WALL W1!H164"),
        FormulaTrace("Total wall depth", "H = RLwall,top - RLbottom",
                     f"{inp.wall_top_rl_m:.3f} - {side_wall_bottom_rl:.3f}", f"{total_wall_depth:.3f} m", "WALL W1!H167"),
    ])
    if is_lsm:
        traces.append(FormulaTrace("Bending coefficient", "Q = 0.1327258645 fck",
                                   f"0.1327258645 x {inp.fck_mpa:.1f}", f"{q:.6f}", "WALL W1!H171 / H64"))
    else:
        traces.append(FormulaTrace("WSM cracking limit", "sigma_bt <= permissible bending tension",
                                   f"fck={inp.fck_mpa:.1f} MPa", f"sigma_bt,allow={permissible_bending_tension(inp.design_code, inp.fck_mpa):.3f} N/mm2",
                                   "IS 3370 legacy cracking-resistance table"))

    wall_results: list[WallStationResult] = []
    for s in inp.wall_stations:
        height = inp.cutoff_height_m if s.label == "Cut-off" else (s.special_height_m if s.fraction is None else total_wall_depth * float(s.fraction))
        water_depth = max(0.0, height - dry_height)
        pressure = inp.gamma_liquid_kn_m3 * water_depth
        m_service = inp.gamma_liquid_kn_m3 * water_depth**3 / 6.0
        m_design = design_factor * m_service
        tension_dia = max(s.vertical_main.dia_mm if s.vertical_main.dia_mm > 0 else 0.0,
                          s.vertical_extra.dia_mm if s.vertical_extra.dia_mm > 0 else 0.0)
        comp_dia = s.vertical_main.dia_mm if s.vertical_main.dia_mm > 0 else tension_dia
        d_eff = s.provided_thickness_mm - inp.wall_cover_mm - tension_dia/2.0
        ast_prov = s.vertical_main.area_per_m() + s.vertical_extra.area_per_m()
        comp_as = s.vertical_main.area_per_m()
        min_ratio = wall_min_ratio_per_face(inp.design_code, inp.design_method, s.provided_thickness_mm, inp.fy_mpa)
        ast_min = min_ratio * 1000.0 * s.provided_thickness_mm

        if is_lsm:
            d_req = _required_depth(m_design, float(q))
            ast_flex, flex_valid = _flexural_ast(m_design, inp.fck_mpa, inp.fy_mpa, d_eff)
        else:
            sigma_t_allow = permissible_bending_tension(inp.design_code, inp.fck_mpa)
            sigma_s_allow = permissible_steel_tension_wsm(inp.design_code, inp.fy_mpa, s.provided_thickness_mm, liquid_face=True)
            sigma_c_allow = permissible_concrete_bending_compression(inp.fck_mpa)
            ast_flex = _wsm_required_ast(
                service_m_knm_m=m_service, h_mm=s.provided_thickness_mm, d_mm=d_eff, cover_mm=inp.wall_cover_mm,
                fck=inp.fck_mpa, tension_dia_mm=max(tension_dia, 8.0), compression_as_mm2=comp_as,
                compression_dia_mm=max(comp_dia, 8.0), sigma_t_allow=sigma_t_allow,
                sigma_s_allow=sigma_s_allow, sigma_c_allow=sigma_c_allow,
            )
            d_req = _wsm_required_thickness(
                service_m_knm_m=m_service, cover_mm=inp.wall_cover_mm, fck=inp.fck_mpa,
                tension_as_mm2=max(ast_prov, 1.0), tension_dia_mm=max(tension_dia, 8.0),
                compression_as_mm2=comp_as, compression_dia_mm=max(comp_dia, 8.0),
                sigma_t_allow=sigma_t_allow, sigma_s_allow=sigma_s_allow, sigma_c_allow=sigma_c_allow,
            )
            flex_valid = ast_flex != float("inf") and d_req != float("inf")

        ast_req = max(ast_flex, ast_min)
        vertical_safe = flex_valid and s.provided_thickness_mm + 1e-9 >= d_req and ast_prov + 1e-9 >= ast_req
        h_req = ast_min
        h_main = s.horizontal_main.area_per_m()
        h_total = h_main + s.horizontal_corner.area_per_m()
        horizontal_safe = h_main + 1e-9 >= h_req
        wall_results.append(WallStationResult(
            label=s.label, height_m=height, water_depth_m=water_depth, pressure_kn_m2=pressure,
            service_moment_knm_m=m_service, factored_moment_knm_m=m_design,
            required_thickness_mm=d_req, provided_thickness_mm=s.provided_thickness_mm,
            effective_depth_mm=d_eff, ast_flexural_mm2_m=ast_flex, ast_min_mm2_m=ast_min,
            ast_required_mm2_m=ast_req, ast_provided_mm2_m=ast_prov,
            vertical_status="SAFE" if vertical_safe else "UNSAFE",
            horizontal_required_mm2_m=h_req, horizontal_main_provided_mm2_m=h_main,
            horizontal_total_provided_mm2_m=h_total,
            horizontal_status="SAFE" if horizontal_safe else "UNSAFE",
        ))
        checks.append(CheckResult(f"Wall vertical design - {s.label}", "SAFE" if vertical_safe else "UNSAFE",
                                  ast_req, ast_prov, "mm2/m", note=f"Required thickness {d_req:.1f} mm; provided {s.provided_thickness_mm:.1f} mm."))
        checks.append(CheckResult(f"Wall horizontal steel - {s.label}", "SAFE" if horizontal_safe else "UNSAFE",
                                  h_req, h_main, "mm2/m", note="Visible check uses main horizontal steel; corner steel is additional."))

    bottom = wall_results[-1]
    bottom_station = inp.wall_stations[-1]
    wall_shear_service = inp.gamma_liquid_kn_m3 * liquid_depth**2 / 2.0
    wall_shear_design = design_factor * wall_shear_service
    wall_tau_v = wall_shear_design * 1e3 / (1000.0 * bottom.effective_depth_mm)
    wall_pt = bottom.ast_provided_mm2_m * 100.0 / (1000.0 * bottom.effective_depth_mm)
    if is_lsm:
        wall_tau_c = shear_strength_tau_c(wall_pt, inp.fck_mpa)
        shear_basis = "IS 456:2000 Table 19"
    elif inp.design_code == CODE_2009:
        wall_tau_c = shear_strength_wsm_2009(wall_pt, inp.fck_mpa)
        shear_basis = "IS 3370:2009 Table 3 (WSM)"
    else:
        wall_tau_c = shear_strength_wsm_1965(inp.fck_mpa)
        shear_basis = "IS 3370:1965 Table 1 cracking shear"
    wall_shear_safe = wall_tau_v <= wall_tau_c
    checks.append(CheckResult("Wall shear", "SAFE" if wall_shear_safe else "UNSAFE", wall_tau_v, wall_tau_c, "N/mm2", note=shear_basis))

    traces.extend([
        FormulaTrace("Bottom wall water pressure", "p = gamma_w h", f"{inp.gamma_liquid_kn_m3:.3f} x {bottom.water_depth_m:.3f}", f"{bottom.pressure_kn_m2:.3f} kN/m2", "WALL W1!D189"),
        FormulaTrace("Bottom wall service moment", "M = gamma_w h^3 / 6", f"{inp.gamma_liquid_kn_m3:.3f} x {bottom.water_depth_m:.3f}^3 / 6", f"{bottom.service_moment_knm_m:.3f} kNm/m", "WALL W1!E189"),
        FormulaTrace("Bottom wall design moment", "Mdesign = factor x Mservice", f"{design_factor:.3f} x {bottom.service_moment_knm_m:.3f}", f"{bottom.factored_moment_knm_m:.3f} kNm/m", "WALL W1!F189 / code method"),
        FormulaTrace("Bottom wall required thickness", "LSM coefficient or WSM stress solution", f"code={inp.design_code}, method={inp.design_method}", f"{bottom.required_thickness_mm:.3f} mm", "Code-specific engine"),
        FormulaTrace("Bottom wall effective depth", "d = D - cover - max(phi)/2", f"{bottom.provided_thickness_mm:.1f} - {inp.wall_cover_mm:.1f} - {max(bottom_station.vertical_main.dia_mm,bottom_station.vertical_extra.dia_mm):.1f}/2", f"{bottom.effective_depth_mm:.3f} mm", "WALL W1!E205"),
        FormulaTrace("Bottom wall required steel", "Ast,req = max(Ast,design, Ast,min)", f"max({bottom.ast_flexural_mm2_m:.3f}, {bottom.ast_min_mm2_m:.3f})", f"{bottom.ast_required_mm2_m:.3f} mm2/m", "Code-specific engine"),
        FormulaTrace("Bottom wall provided steel", "Ast,prov = sum(pi phi^2/4 x 1000/s)", f"{bottom_station.vertical_main.dia_mm:g}@{bottom_station.vertical_main.spacing_mm:g} + {bottom_station.vertical_extra.dia_mm:g}@{bottom_station.vertical_extra.spacing_mm:g}", f"{bottom.ast_provided_mm2_m:.3f} mm2/m", "WALL W1!G224"),
        FormulaTrace("Wall shear stress", "tau_v = Vdesign/(b d)", f"{wall_shear_design:.3f} x 10^3/(1000 x {bottom.effective_depth_mm:.1f})", f"{wall_tau_v:.4f} N/mm2", "Visible wall shear check"),
        FormulaTrace("Wall shear capacity", shear_basis, f"pt={wall_pt:.4f}%, fck={inp.fck_mpa:.1f}", f"{wall_tau_c:.4f} N/mm2", "Code-specific shear basis"),
    ])

    if is_lsm:
        wall_crack = _crack_width(
            service_m_knm_m=bottom.service_moment_knm_m, as_mm2_m=bottom.ast_provided_mm2_m,
            b_mm=1000.0, h_mm=bottom.provided_thickness_mm, cover_mm=inp.wall_cover_mm,
            d_mm=bottom.effective_depth_mm, fck=inp.fck_mpa, fy=inp.fy_mpa,
            bar_dia_mm=max(bottom_station.vertical_main.dia_mm, bottom_station.vertical_extra.dia_mm),
            effective_spacing_mm=min(x for x in [bottom_station.vertical_main.spacing_mm, bottom_station.vertical_extra.spacing_mm] if x > 0)/2.0,
        )
        conc_cap = float(prof.crack_concrete_factor) * inp.fck_mpa
        steel_cap = float(prof.crack_steel_factor) * inp.fy_mpa
        wall_conc_safe = float(wall_crack["fcb_mpa"]) <= conc_cap
        wall_steel_safe = float(wall_crack["fs_mpa"]) <= steel_cap
        wall_crack_safe = float(wall_crack["wcr_mm"]) <= inp.crack_limit_mm
        checks.extend([
            CheckResult("Wall crack check - concrete stress", "SAFE" if wall_conc_safe else "UNSAFE", float(wall_crack["fcb_mpa"]), conc_cap, "N/mm2"),
            CheckResult("Wall crack check - steel stress", "SAFE" if wall_steel_safe else "UNSAFE", float(wall_crack["fs_mpa"]), steel_cap, "N/mm2"),
            CheckResult("Wall crack width", "SAFE" if wall_crack_safe else "UNSAFE", float(wall_crack["wcr_mm"]), inp.crack_limit_mm, "mm"),
        ])
        traces.append(FormulaTrace("Wall crack width", "wcr = 3 acr eps_m/[1+2(acr-c)/(h-x)]",
                                   f"acr={wall_crack['acr_mm']:.3f}, eps_m={wall_crack['eps_m']:.7f}", f"{wall_crack['wcr_mm']:.2f} mm", "IS 3370 Annex B / WALL W1 visible crack block"))
    else:
        tension_as = bottom.ast_provided_mm2_m
        comp_as = bottom_station.vertical_main.area_per_m()
        unc = _wsm_uncracked_stress(
            service_m_knm_m=bottom.service_moment_knm_m, h_mm=bottom.provided_thickness_mm,
            cover_mm=inp.wall_cover_mm, fck=inp.fck_mpa, tension_as_mm2=tension_as,
            tension_dia_mm=max(bottom_station.vertical_main.dia_mm, bottom_station.vertical_extra.dia_mm),
            compression_as_mm2=comp_as, compression_dia_mm=bottom_station.vertical_main.dia_mm,
        )
        cr = _wsm_cracked_stresses(bottom.service_moment_knm_m, tension_as, bottom.effective_depth_mm, inp.fck_mpa)
        tcap = permissible_bending_tension(inp.design_code, inp.fck_mpa)
        scap = permissible_steel_tension_wsm(inp.design_code, inp.fy_mpa, bottom.provided_thickness_mm, liquid_face=True)
        ccap = permissible_concrete_bending_compression(inp.fck_mpa)
        checks.extend([
            CheckResult("Wall cracking resistance - concrete bending tension", "SAFE" if unc["sigma_t_mpa"] <= tcap else "UNSAFE", unc["sigma_t_mpa"], tcap, "N/mm2"),
            CheckResult("Wall WSM steel stress", "SAFE" if cr["fs_mpa"] <= scap else "UNSAFE", cr["fs_mpa"], scap, "N/mm2"),
            CheckResult("Wall WSM concrete compression", "SAFE" if cr["fcb_mpa"] <= ccap else "UNSAFE", cr["fcb_mpa"], ccap, "N/mm2"),
        ])
        wall_crack = {"applicable": False, "mode": "WSM stress control", "wcr_mm": None,
                      "concrete_tension_mpa": unc["sigma_t_mpa"], "concrete_tension_allow_mpa": tcap,
                      "fs_mpa": cr["fs_mpa"], "steel_allow_mpa": scap, "fcb_mpa": cr["fcb_mpa"], "concrete_allow_mpa": ccap,
                      "x_mm": cr["x_mm"], "z_mm": cr["z_mm"]}
        traces.append(FormulaTrace("Wall cracking resistance", "sigma_bt = M y/I <= permissible bending tension",
                                   f"M={bottom.service_moment_knm_m:.3f} kNm/m; transformed uncracked section", f"{unc['sigma_t_mpa']:.3f} <= {tcap:.3f} N/mm2", "IS 3370 legacy WSM cracking basis"))

    # Footing geometry and stability — visible Inside Liquid Pressure case.
    # The original workbook used equal heel/toe projections. The web app now exposes
    # them independently while preserving the same visible equilibrium methodology.
    toe = inp.toe_projection_m
    heel = inp.heel_projection_m
    bwall_top = wall_top_thk_m
    bwall_base = wall_base_thk_m
    base_width = toe + bwall_base + heel
    edge_t = inp.footing_edge_thickness_m
    total_t = inp.footing_total_thickness_m
    haunch = total_t - edge_t
    taper_delta = bwall_base - bwall_top
    if taper_delta < -1e-9:
        warnings.append("Base wall thickness is less than top wall thickness; the workbook taper-weight model is outside its intended geometry.")

    ot_force = inp.gamma_liquid_kn_m3 * liquid_depth**2 / 2.0
    overturning_m = ot_force * (liquid_depth/3.0 + total_t)
    W1 = bwall_top * total_wall_depth * inp.gamma_concrete_kn_m3
    la1 = toe + taper_delta + bwall_top/2.0
    W2 = 0.5 * taper_delta * inp.wall_taper_height_m * inp.gamma_concrete_kn_m3
    la2 = toe + (2.0/3.0)*taper_delta if abs(taper_delta) > 1e-12 else toe
    W3 = base_width * edge_t * inp.gamma_concrete_kn_m3
    la3 = base_width/2.0
    W5 = 0.5 * toe * haunch * inp.gamma_concrete_kn_m3
    la5 = (2.0/3.0)*toe
    W6 = 0.5 * heel * haunch * inp.gamma_concrete_kn_m3
    la6 = toe + bwall_base + heel/3.0
    W4 = heel * liquid_depth * inp.gamma_liquid_kn_m3
    la4 = toe + bwall_base + heel/2.0
    W9 = 0.5 * heel * haunch * inp.gamma_liquid_kn_m3
    la9 = toe + bwall_base + (2.0/3.0)*heel
    weights = [W1, W2, W3, W5, W6, W4, W9]
    moments = [W1*la1, W2*la2, W3*la3, W5*la5, W6*la6, W4*la4, W9*la9]
    total_weight = sum(weights)
    gross_stab_m = sum(moments)
    net_stab_m = gross_stab_m - overturning_m
    fos = gross_stab_m/overturning_m if overturning_m > 0 else float("inf")
    x_from_toe = net_stab_m/total_weight if total_weight > 0 else float("nan")
    e = base_width/2.0 - x_from_toe
    e_abs = abs(e)
    e_allow = base_width/6.0
    pmax = total_weight/base_width * (1.0 + 6.0*e_abs/base_width)
    pmin = total_weight/base_width * (1.0 - 6.0*e_abs/base_width)
    checks.extend([
        CheckResult("Footing factor of safety", "SAFE" if fos >= inp.allowable_fos else "UNSAFE", inp.allowable_fos, fos, "", note="Capacity column shows calculated FOS."),
        CheckResult("Footing eccentricity", "SAFE" if e_abs <= e_allow else "UNSAFE", e_abs, e_allow, "m"),
        CheckResult("Maximum soil pressure", "SAFE" if pmax <= inp.sbc_kn_m2 else "UNSAFE", pmax, inp.sbc_kn_m2, "kN/m2"),
        CheckResult("Minimum soil pressure / no tension", "SAFE" if (pmin >= 0.0 and pmin <= inp.sbc_kn_m2) else "UNSAFE", pmin, 0.0, "kN/m2", note="Requires pmin >= 0; SBC upper bound also checked."),
    ])

    slope = (pmax-pmin)/base_width
    p_wall_toe = pmin + slope*(heel+bwall_base)
    p_wall_heel = pmin + slope*heel
    hd1 = heel*total_t*inp.gamma_concrete_kn_m3*(heel/2.0)
    hd2 = heel*liquid_depth*inp.gamma_liquid_kn_m3*(heel/2.0)
    hd3 = 0.5*heel*haunch*inp.gamma_liquid_kn_m3*((2.0/3.0)*heel)
    hd4 = 0.5*heel*haunch*inp.gamma_concrete_kn_m3*(heel/3.0)
    heel_down_m = hd1+hd2+hd3+hd4
    hu1 = pmin*heel*(heel/2.0)
    hu2 = 0.5*(p_wall_heel-pmin)*heel*(heel/3.0)
    heel_up_m = hu1+hu2
    heel_m = heel_down_m-heel_up_m
    td1 = toe*edge_t*inp.gamma_concrete_kn_m3*(toe/2.0)
    td2 = 0.5*toe*haunch*inp.gamma_concrete_kn_m3*((2.0/3.0)*toe)
    toe_down_m = td1+td2
    tu1 = p_wall_toe*toe*(toe/2.0)
    tu2 = 0.5*(pmax-p_wall_toe)*toe*((2.0/3.0)*toe)
    toe_up_m = tu1+tu2
    toe_m = toe_down_m-toe_up_m

    top_service_m = max(heel_m, toe_m, 0.0)
    bottom_service_m = max(-heel_m, -toe_m, 0.0)
    top_design_m = design_factor*top_service_m
    bottom_design_m = design_factor*bottom_service_m
    governing_service_m = max(abs(heel_m), abs(toe_m))
    governing_design_m = design_factor*governing_service_m

    top_as_prov = _bar_area(inp.footing_top_layers)
    bottom_as_prov = _bar_area(inp.footing_bottom_layers)
    top_dia = max(_max_dia(inp.footing_top_layers), 8.0)
    bottom_dia = max(_max_dia(inp.footing_bottom_layers), 8.0)
    top_d = total_t*1000.0 - inp.footing_cover_mm - top_dia/2.0
    bottom_d = total_t*1000.0 - inp.footing_cover_mm - bottom_dia/2.0
    avg_t_mm = (total_t+edge_t)/2.0*1000.0
    foot_min_ratio = footing_min_ratio_per_face(inp.design_code, inp.design_method, avg_t_mm, inp.fy_mpa)
    foot_min_as = foot_min_ratio*1000.0*avg_t_mm

    if is_lsm:
        footing_required_thk = sqrt(governing_design_m*1e6/(float(q)*1000.0)) if governing_design_m > 0 else 0.0
        top_ast_flex, top_flex_valid = _flexural_ast(top_design_m, inp.fck_mpa, inp.fy_mpa, top_d)
        bot_ast_flex, bot_flex_valid = _flexural_ast(bottom_design_m, inp.fck_mpa, inp.fy_mpa, bottom_d)
    else:
        tcap = permissible_bending_tension(inp.design_code, inp.fck_mpa)
        scap_top = permissible_steel_tension_wsm(inp.design_code, inp.fy_mpa, total_t*1000.0, liquid_face=True)
        scap_bottom = permissible_steel_tension_wsm(inp.design_code, inp.fy_mpa, total_t*1000.0, liquid_face=True)
        ccap = permissible_concrete_bending_compression(inp.fck_mpa)
        top_ast_flex = _wsm_required_ast(
            service_m_knm_m=top_service_m, h_mm=total_t*1000.0, d_mm=top_d, cover_mm=inp.footing_cover_mm,
            fck=inp.fck_mpa, tension_dia_mm=top_dia, compression_as_mm2=bottom_as_prov, compression_dia_mm=bottom_dia,
            sigma_t_allow=tcap, sigma_s_allow=scap_top, sigma_c_allow=ccap,
        )
        bot_ast_flex = _wsm_required_ast(
            service_m_knm_m=bottom_service_m, h_mm=total_t*1000.0, d_mm=bottom_d, cover_mm=inp.footing_cover_mm,
            fck=inp.fck_mpa, tension_dia_mm=bottom_dia, compression_as_mm2=top_as_prov, compression_dia_mm=top_dia,
            sigma_t_allow=tcap, sigma_s_allow=scap_bottom, sigma_c_allow=ccap,
        )
        top_req_h = _wsm_required_thickness(
            service_m_knm_m=top_service_m, cover_mm=inp.footing_cover_mm, fck=inp.fck_mpa,
            tension_as_mm2=max(top_as_prov,1.0), tension_dia_mm=top_dia, compression_as_mm2=bottom_as_prov,
            compression_dia_mm=bottom_dia, sigma_t_allow=tcap, sigma_s_allow=scap_top, sigma_c_allow=ccap,
        )
        bot_req_h = _wsm_required_thickness(
            service_m_knm_m=bottom_service_m, cover_mm=inp.footing_cover_mm, fck=inp.fck_mpa,
            tension_as_mm2=max(bottom_as_prov,1.0), tension_dia_mm=bottom_dia, compression_as_mm2=top_as_prov,
            compression_dia_mm=top_dia, sigma_t_allow=tcap, sigma_s_allow=scap_bottom, sigma_c_allow=ccap,
        )
        footing_required_thk = max(top_req_h, bot_req_h)
        top_flex_valid = top_ast_flex != float("inf")
        bot_flex_valid = bot_ast_flex != float("inf")

    footing_thk_safe = total_t*1000.0 + 1e-9 >= footing_required_thk
    checks.append(CheckResult("Footing required thickness", "SAFE" if footing_thk_safe else "UNSAFE", footing_required_thk, total_t*1000.0, "mm"))
    top_ast_req = max(top_ast_flex, foot_min_as)
    bot_ast_req = max(bot_ast_flex, foot_min_as)
    top_reinf_safe = top_flex_valid and top_as_prov + 1e-9 >= top_ast_req
    bot_reinf_safe = bot_flex_valid and bottom_as_prov + 1e-9 >= bot_ast_req
    dist_top = _bar_area(inp.footing_distribution_top)
    dist_bottom = _bar_area(inp.footing_distribution_bottom)
    checks.extend([
        CheckResult("Footing top reinforcement", "SAFE" if top_reinf_safe else "UNSAFE", top_ast_req, top_as_prov, "mm2/m"),
        CheckResult("Footing bottom reinforcement", "SAFE" if bot_reinf_safe else "UNSAFE", bot_ast_req, bottom_as_prov, "mm2/m"),
        CheckResult("Footing top distribution steel", "SAFE" if dist_top >= foot_min_as else "UNSAFE", foot_min_as, dist_top, "mm2/m"),
        CheckResult("Footing bottom distribution steel", "SAFE" if dist_bottom >= foot_min_as else "UNSAFE", foot_min_as, dist_bottom, "mm2/m"),
    ])

    heel_pt = top_as_prov*100.0/(1000.0*top_d)
    heel_reaction = pmin*heel + 0.5*(p_wall_heel-pmin)*heel
    heel_v_design = design_factor*heel_reaction
    heel_tau_v = heel_v_design*1e3/(1000.0*top_d)
    toe_pt = bottom_as_prov*100.0/(1000.0*bottom_d)
    toe_reaction = p_wall_toe*toe + 0.5*(pmax-p_wall_toe)*toe
    toe_v_design = design_factor*toe_reaction
    toe_tau_v = toe_v_design*1e3/(1000.0*bottom_d)
    if is_lsm:
        heel_tau_c = shear_strength_tau_c(heel_pt, inp.fck_mpa)
        toe_tau_c = shear_strength_tau_c(toe_pt, inp.fck_mpa)
    elif inp.design_code == CODE_2009:
        heel_tau_c = shear_strength_wsm_2009(heel_pt, inp.fck_mpa)
        toe_tau_c = shear_strength_wsm_2009(toe_pt, inp.fck_mpa)
    else:
        heel_tau_c = shear_strength_wsm_1965(inp.fck_mpa)
        toe_tau_c = shear_strength_wsm_1965(inp.fck_mpa)
    checks.extend([
        CheckResult("Footing shear - heel", "SAFE" if heel_tau_v <= heel_tau_c else "UNSAFE", heel_tau_v, heel_tau_c, "N/mm2"),
        CheckResult("Footing shear - toe", "SAFE" if toe_tau_v <= toe_tau_c else "UNSAFE", toe_tau_v, toe_tau_c, "N/mm2"),
    ])

    traces.extend([
        FormulaTrace("Footing base width", "B = toe projection + wall base thickness + heel projection", f"{toe:.3f} + {bwall_base:.3f} + {heel:.3f}", f"{base_width:.3f} m", "Visible footing geometry - generalized for independent projections"),
        FormulaTrace("Toe / heel projections", "Independent geometry inputs", f"toe={toe:.3f} m; heel={heel:.3f} m", f"toe={toe:.3f} m; heel={heel:.3f} m", "Web-app input / visible footing geometry"),
        FormulaTrace("Footing FOS", "FOS = gross stabilising moment/overturning moment", f"{gross_stab_m:.3f}/{overturning_m:.3f}", f"{fos:.4f}", "WALL W1!G670"),
        FormulaTrace("Footing eccentricity", "e = B/2 - x; check |e| <= B/6", f"{base_width:.3f}/2 - {x_from_toe:.3f}", f"{e:.4f} m; |e|={e_abs:.4f} m", "WALL W1!F676"),
        FormulaTrace("Maximum bearing pressure", "pmax = W/B[1+6|e|/B]", f"{total_weight:.3f}/{base_width:.3f} x [1+6x{e_abs:.4f}/{base_width:.3f}]", f"{pmax:.3f} kN/m2", "WALL W1!H680"),
        FormulaTrace("Minimum bearing pressure", "pmin = W/B[1-6|e|/B]", f"{total_weight:.3f}/{base_width:.3f} x [1-6x{e_abs:.4f}/{base_width:.3f}]", f"{pmin:.3f} kN/m2", "WALL W1!H683"),
        FormulaTrace("Heel net moment", "Mheel = Mdown - Mup", f"{heel_down_m:.3f}-{heel_up_m:.3f}", f"{heel_m:.3f} kNm/m", "WALL W1!I706"),
        FormulaTrace("Toe net moment", "Mtoe = Mdown - Mup", f"{toe_down_m:.3f}-{toe_up_m:.3f}", f"{toe_m:.3f} kNm/m", "WALL W1!I718"),
        FormulaTrace("Governing footing design moment", "Mdesign = factor x MAX(|Mheel|,|Mtoe|)", f"{design_factor:.2f} x MAX(|{heel_m:.3f}|,|{toe_m:.3f}|)", f"{governing_design_m:.3f} kNm/m", "Code-specific design action"),
        FormulaTrace("Required footing thickness", "LSM coefficient or WSM stress solution", f"code={inp.design_code}, method={inp.design_method}", f"{footing_required_thk:.3f} mm", "Code-specific engine"),
        FormulaTrace("Footing top effective depth", "dtop = D-cover-max(phi_top)/2", f"{total_t*1000:.1f}-{inp.footing_cover_mm:.1f}-{top_dia:.1f}/2", f"{top_d:.3f} mm", "WALL W1!I732"),
        FormulaTrace("Footing bottom effective depth", "dbot = D-cover-max(phi_bottom)/2", f"{total_t*1000:.1f}-{inp.footing_cover_mm:.1f}-{bottom_dia:.1f}/2", f"{bottom_d:.3f} mm", "WALL W1!I737"),
        FormulaTrace("Footing top steel required", "Ast,req=max(Ast,design,Ast,min)", f"max({top_ast_flex:.3f},{foot_min_as:.3f})", f"{top_ast_req:.3f} mm2/m", "Code-specific engine"),
        FormulaTrace("Footing bottom steel required", "Ast,req=max(Ast,design,Ast,min)", f"max({bot_ast_flex:.3f},{foot_min_as:.3f})", f"{bot_ast_req:.3f} mm2/m", "Code-specific engine"),
    ])

    if is_lsm and top_service_m > 0 and top_as_prov > 0:
        top_active = [l for l in inp.footing_top_layers if l.dia_mm > 0 and l.spacing_mm > 0]
        crack_bar = max(l.dia_mm for l in top_active)
        crack_spacing = min(l.spacing_mm for l in top_active)/2.0
        foot_crack = _crack_width(
            service_m_knm_m=top_service_m, as_mm2_m=top_as_prov, b_mm=1000.0, h_mm=total_t*1000.0,
            cover_mm=inp.footing_cover_mm, d_mm=top_d, fck=inp.fck_mpa, fy=inp.fy_mpa,
            bar_dia_mm=crack_bar, effective_spacing_mm=crack_spacing,
        )
        conc_cap = float(prof.crack_concrete_factor)*inp.fck_mpa
        steel_cap = float(prof.crack_steel_factor)*inp.fy_mpa
        checks.extend([
            CheckResult("Footing crack check - concrete stress", "SAFE" if float(foot_crack["fcb_mpa"]) <= conc_cap else "UNSAFE", float(foot_crack["fcb_mpa"]), conc_cap, "N/mm2"),
            CheckResult("Footing crack check - steel stress", "SAFE" if float(foot_crack["fs_mpa"]) <= steel_cap else "UNSAFE", float(foot_crack["fs_mpa"]), steel_cap, "N/mm2"),
            CheckResult("Footing crack width (visible top/heel check)", "SAFE" if float(foot_crack["wcr_mm"]) <= inp.crack_limit_mm else "UNSAFE", float(foot_crack["wcr_mm"]), inp.crack_limit_mm, "mm"),
        ])
        traces.append(FormulaTrace("Footing crack width", "wcr = Annex B mature-concrete flexural expression", f"acr={foot_crack['acr_mm']:.3f}, eps_m={foot_crack['eps_m']:.7f}", f"{foot_crack['wcr_mm']:.2f} mm", "WALL W1!H878 / selected code Annex B"))
    elif not is_lsm and top_service_m > 0 and top_as_prov > 0:
        unc = _wsm_uncracked_stress(
            service_m_knm_m=top_service_m, h_mm=total_t*1000.0, cover_mm=inp.footing_cover_mm, fck=inp.fck_mpa,
            tension_as_mm2=top_as_prov, tension_dia_mm=top_dia, compression_as_mm2=bottom_as_prov, compression_dia_mm=bottom_dia,
        )
        cr = _wsm_cracked_stresses(top_service_m, top_as_prov, top_d, inp.fck_mpa)
        tcap = permissible_bending_tension(inp.design_code, inp.fck_mpa)
        scap = permissible_steel_tension_wsm(inp.design_code, inp.fy_mpa, total_t*1000.0, liquid_face=True)
        ccap = permissible_concrete_bending_compression(inp.fck_mpa)
        checks.extend([
            CheckResult("Footing cracking resistance - concrete bending tension", "SAFE" if unc["sigma_t_mpa"] <= tcap else "UNSAFE", unc["sigma_t_mpa"], tcap, "N/mm2"),
            CheckResult("Footing WSM steel stress (visible top/heel check)", "SAFE" if cr["fs_mpa"] <= scap else "UNSAFE", cr["fs_mpa"], scap, "N/mm2"),
            CheckResult("Footing WSM concrete compression (visible top/heel check)", "SAFE" if cr["fcb_mpa"] <= ccap else "UNSAFE", cr["fcb_mpa"], ccap, "N/mm2"),
        ])
        foot_crack = {"applicable": False, "mode": "WSM stress control", "wcr_mm": None,
                      "concrete_tension_mpa": unc["sigma_t_mpa"], "concrete_tension_allow_mpa": tcap,
                      "fs_mpa": cr["fs_mpa"], "steel_allow_mpa": scap, "fcb_mpa": cr["fcb_mpa"], "concrete_allow_mpa": ccap,
                      "x_mm": cr["x_mm"], "z_mm": cr["z_mm"]}
        traces.append(FormulaTrace("Footing cracking resistance", "sigma_bt = M y/I <= permissible bending tension", f"M={top_service_m:.3f} kNm/m", f"{unc['sigma_t_mpa']:.3f} <= {tcap:.3f} N/mm2", "Legacy WSM / visible top-heel serviceability scope"))
    else:
        foot_crack = {"applicable": False, "wcr_mm": None if not is_lsm else 0.0, "fs_mpa": 0.0, "fcb_mpa": 0.0}
        checks.append(CheckResult("Footing serviceability (visible top/heel check)", "N/A", note="No positive/top-face service moment.", mandatory=False))

    warnings.append("The visible workbook contains a footing serviceability calculation for the top/heel face only; a separate bottom/toe crack/serviceability block is outside the implemented visible scope.")
    warnings.append("Outside-soil-pressure and other hidden workbook modules are not included. Hidden cells are used only where needed to reproduce a visible calculation dependency.")
    warnings.append("QD-003 (WALL W1!M200 = #REF!) is intentionally excluded from the engine per user instruction.")

    wall_check_names = [c for c in checks if c.name.startswith("Wall")]
    footing_check_names = [c for c in checks if c.name.startswith("Footing") or c.name.startswith("Maximum soil") or c.name.startswith("Minimum soil")]
    wall_status = "SAFE" if all(c.status != "UNSAFE" for c in wall_check_names if c.mandatory) else "UNSAFE"
    footing_status = "SAFE" if all(c.status != "UNSAFE" for c in footing_check_names if c.mandatory) else "UNSAFE"
    overall = "SAFE" if all(c.status != "UNSAFE" for c in checks if c.mandatory) else "UNSAFE"

    wall = {
        "design_code": inp.design_code, "design_method": inp.design_method,
        "side_wall_bottom_rl_m": side_wall_bottom_rl, "liquid_depth_m": liquid_depth,
        "total_wall_depth_m": total_wall_depth, "dry_height_m": dry_height,
        "bm_coefficient": q, "bottom_service_moment_knm_m": bottom.service_moment_knm_m,
        "bottom_factored_moment_knm_m": bottom.factored_moment_knm_m,
        "bottom_required_thickness_mm": bottom.required_thickness_mm,
        "bottom_effective_depth_mm": bottom.effective_depth_mm,
        "bottom_ast_required_mm2_m": bottom.ast_required_mm2_m,
        "bottom_ast_provided_mm2_m": bottom.ast_provided_mm2_m,
        "shear_force_service_kn": wall_shear_service, "shear_force_design_kn": wall_shear_design,
        "pt_percent": wall_pt, "tau_v_mpa": wall_tau_v, "tau_c_mpa": wall_tau_c,
        "shear_basis": shear_basis, "crack": wall_crack,
    }
    footing = {
        "design_code": inp.design_code, "design_method": inp.design_method,
        "toe_projection_m": toe, "heel_projection_m": heel,
        "base_width_m": base_width, "wall_top_thickness_m": bwall_top, "wall_base_thickness_m": bwall_base,
        "haunch_thickness_m": haunch, "overturning_moment_knm": overturning_m, "total_weight_kn": total_weight,
        "gross_stabilising_moment_knm": gross_stab_m, "net_stabilising_moment_knm": net_stab_m,
        "fos": fos, "x_from_toe_m": x_from_toe, "eccentricity_m": e, "eccentricity_abs_m": e_abs,
        "eccentricity_allow_m": e_allow, "pmax_kn_m2": pmax, "pmin_kn_m2": pmin,
        "p_wall_toe_kn_m2": p_wall_toe, "p_wall_heel_kn_m2": p_wall_heel,
        "heel_moment_knm_m": heel_m, "toe_moment_knm_m": toe_m,
        "governing_service_moment_knm_m": governing_service_m, "governing_factored_moment_knm_m": governing_design_m,
        "required_thickness_mm": footing_required_thk, "provided_thickness_mm": total_t*1000.0,
        "top_effective_depth_mm": top_d, "bottom_effective_depth_mm": bottom_d, "min_ast_mm2_m": foot_min_as,
        "top_service_moment_knm_m": top_service_m, "bottom_service_moment_knm_m": bottom_service_m,
        "top_ast_required_mm2_m": top_ast_req, "bottom_ast_required_mm2_m": bot_ast_req,
        "top_ast_provided_mm2_m": top_as_prov, "bottom_ast_provided_mm2_m": bottom_as_prov,
        "distribution_top_mm2_m": dist_top, "distribution_bottom_mm2_m": dist_bottom,
        "heel_pt_percent": heel_pt, "heel_tau_v_mpa": heel_tau_v, "heel_tau_c_mpa": heel_tau_c,
        "toe_pt_percent": toe_pt, "toe_tau_v_mpa": toe_tau_v, "toe_tau_c_mpa": toe_tau_c,
        "crack": foot_crack,
    }

    return DesignResult(
        inputs=inp, overall_status=overall, wall_status=wall_status, footing_status=footing_status,
        wall_stations=wall_results, wall=wall, footing=footing, checks=checks,
        formula_trace=traces, warnings=warnings, reconciliation_notes=list(CORRECTION_NOTES),
    )


def linked_wall_thickness_profile(
    stations: list[WallStationInput], edited_index: int, edited_thickness_mm: float
) -> list[float]:
    """Return a linked wall-thickness schedule after one station is edited.

    The approved station-to-station profile is preserved exactly by applying the same
    additive thickness change (delta) to every station. This matches the thickness-only
    optimiser, keeps the taper/plateau shape unchanged, and ensures all linked values
    remain visible and auditable in the UI.
    """
    if not stations:
        raise ValueError("Wall station schedule is empty.")
    if edited_index < 0 or edited_index >= len(stations):
        raise IndexError("Edited wall-station index is outside the schedule.")
    if edited_thickness_mm <= 0:
        raise ValueError("Edited wall thickness must be greater than zero.")
    delta = float(edited_thickness_mm) - float(stations[edited_index].provided_thickness_mm)
    return [float(s.provided_thickness_mm) + delta for s in stations]


def recommend_safe_thickness(inp: DesignInputs, step_mm: int = 25, max_increase_mm: int = 500) -> dict:
    """Thickness-only optimiser using the currently selected code and method."""
    baseline = calculate(inp)
    if baseline.overall_status == "SAFE":
        return {"found": True, "already_safe": True, "inputs": inp, "result": baseline,
                "wall_increase_mm": 0, "footing_increase_mm": 0, "governing_failed_checks": []}
    failures = [c.name for c in baseline.failed_checks()]
    increments = list(range(0, max_increase_mm + step_mm, step_mm))
    candidates = sorted(((wi, fi) for wi in increments for fi in increments if wi or fi),
                        key=lambda x: (x[0]+x[1], max(x), x[0], x[1]))
    for wall_inc, foot_inc in candidates:
        trial = deepcopy(inp)
        if wall_inc:
            for s in trial.wall_stations:
                s.provided_thickness_mm += wall_inc
        if foot_inc:
            trial.footing_total_thickness_m += foot_inc/1000.0
        try:
            r = calculate(trial)
        except ValueError:
            continue
        if r.overall_status == "SAFE":
            return {"found": True, "already_safe": False, "inputs": trial, "result": r,
                    "wall_increase_mm": wall_inc, "footing_increase_mm": foot_inc,
                    "governing_failed_checks": failures}
    return {"found": False, "already_safe": False, "inputs": None, "result": None,
            "wall_increase_mm": None, "footing_increase_mm": None,
            "governing_failed_checks": failures,
            "message": "No valid thickness-only solution was found within the permitted range."}
