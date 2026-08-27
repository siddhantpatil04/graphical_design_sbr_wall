from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

CODE_1965 = "IS 3370:1965"
CODE_2009 = "IS 3370:2009"
CODE_2021 = "IS 3370:2021"

METHOD_WSM = "Working Stress Design"
METHOD_LSM = "Limit State Design"

CODE_OPTIONS = [CODE_2021, CODE_2009, CODE_1965]

# Concrete tensile stress limits for resistance to cracking, N/mm2.
# 1965 Table 1 and 2009 Table 1 are the same for overlapping grades.
CRACK_TENSION_DIRECT = {
    15: 1.1, 20: 1.2, 25: 1.3, 30: 1.5, 35: 1.6, 40: 1.7,
    45: 2.0, 50: 2.1,
}
CRACK_TENSION_BENDING = {
    15: 1.5, 20: 1.7, 25: 1.8, 30: 2.0, 35: 2.2, 40: 2.4,
    45: 2.6, 50: 2.8,
}

# Working-stress permissible concrete compression in bending, N/mm2.
# 2009 Table 2; M30=10 N/mm2 is also the value used in the supplied workbook's WSM basis.
WSM_CONCRETE_BENDING_COMPRESSION = {
    15: 5.0, 20: 7.0, 25: 8.5, 30: 10.0, 35: 11.5, 40: 13.0,
    45: 14.5, 50: 16.0,
}

# 1965 Table 1: permissible total shear stress for resistance to cracking, N/mm2.
SHEAR_CRACK_1965 = {15: 1.5, 20: 1.7, 25: 1.9, 30: 2.2, 35: 2.4, 40: 2.7}

# 2009 Table 3: permissible shear stress in concrete for WSM, N/mm2.
PT_POINTS_2009 = [0.15, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50, 2.75, 3.00]
SHEAR_2009_WSM = {
    25: [0.19, 0.23, 0.31, 0.36, 0.40, 0.44, 0.46, 0.49, 0.51, 0.53, 0.55, 0.56, 0.57],
    30: [0.20, 0.23, 0.31, 0.37, 0.41, 0.45, 0.47, 0.50, 0.53, 0.55, 0.57, 0.58, 0.60],
    35: [0.20, 0.23, 0.31, 0.37, 0.42, 0.45, 0.49, 0.52, 0.54, 0.56, 0.58, 0.60, 0.62],
    40: [0.20, 0.23, 0.32, 0.38, 0.42, 0.46, 0.49, 0.52, 0.55, 0.57, 0.60, 0.62, 0.63],
}


@dataclass(frozen=True)
class CodeProfile:
    code: str
    method: str
    explicit_crack_width: bool
    crack_steel_factor: float | None
    crack_concrete_factor: float | None
    notes: tuple[str, ...]


def normalise_method(code: str, method: str | None) -> str:
    if code == CODE_1965:
        return METHOD_WSM
    if code == CODE_2021:
        return METHOD_LSM
    if code == CODE_2009:
        return method if method in (METHOD_LSM, METHOD_WSM) else METHOD_LSM
    raise ValueError(f"Unsupported design code: {code}")


def profile(code: str, method: str | None = None) -> CodeProfile:
    method = normalise_method(code, method)
    if code == CODE_2021:
        return CodeProfile(
            code, method, True, 0.60, 0.40,
            (
                "IS 3370 (Part 2):2021 uses limit-state design; working-stress design was removed.",
                "Calculated crack width is limited to the selected limit (normally not more than 0.2 mm).",
                "Annex B stress prerequisites used here: steel stress <= 0.6 fy and concrete stress <= 0.4 fck.",
                "The visible workbook minimum wall/footing reinforcement basis is retained as 0.36% of each surface zone, equivalent to 0.18% of gross thickness per face for D < 500 mm.",
            ),
        )
    if code == CODE_2009 and method == METHOD_LSM:
        return CodeProfile(
            code, method, True, 0.80, 0.45,
            (
                "IS 3370 (Part 2):2009 permits either limit-state or working-stress design; this branch uses limit-state design.",
                "Annex B stress prerequisites used here: steel stress <= 0.8 fy and concrete stress <= 0.45 fck.",
                "Clause 8.1.1 minimum reinforcement uses 0.35% of each surface zone for high-strength deformed bars. The <=15 m reduction to 0.24% is not invoked because that plan dimension is outside the visible W1 workbook scope.",
            ),
        )
    if code == CODE_2009 and method == METHOD_WSM:
        return CodeProfile(
            code, method, False, None, None,
            (
                "IS 3370 (Part 2):2009 permits working-stress design as an alternative method.",
                "Cracking resistance is checked by permissible concrete tensile stress (Table 1); strength is checked by working-stress concrete/steel limits.",
                "Clause 8.1.1 minimum reinforcement uses 0.35% of each surface zone for high-strength deformed bars. The <=15 m reduction is not invoked because the relevant plan dimension is outside the visible scope.",
            ),
        )
    if code == CODE_1965:
        return CodeProfile(
            code, method, False, None, None,
            (
                "IS 3370 (Part II):1965 is implemented by the working-stress / resistance-to-cracking basis of the legacy code.",
                "Concrete tensile stress is checked against Table 1; steel strength stress is capped at the legacy HYSD permissible value rather than the modern fy value.",
                "Minimum reinforcement follows Clause 7.1.1, including the 20% reduction for high-yield deformed bars and two-face distribution for sections >=225 mm.",
                "For modern Fe500/Fe550 selections, the legacy HYSD permissible stress is still capped at the 1965 table value; the code did not contain modern Fe500/Fe550 grade-specific limits.",
            ),
        )
    raise ValueError(f"Unsupported design code/method combination: {code} / {method}")


def _grade_key(value: float, allowed: list[int]) -> int:
    keys = sorted(allowed)
    if value < keys[0]:
        raise ValueError(f"Concrete grade M{value:g} is below the implemented code table range.")
    # use exact grade where available; otherwise next lower tabulated grade conservatively
    eligible = [k for k in keys if k <= value]
    return max(eligible)


def permissible_bending_tension(code: str, fck: float) -> float:
    allowed = [15, 20, 25, 30, 35, 40] if code == CODE_1965 else [25, 30, 35, 40, 45, 50]
    k = _grade_key(fck, allowed)
    return CRACK_TENSION_BENDING[k]


def permissible_direct_tension(code: str, fck: float) -> float:
    allowed = [15, 20, 25, 30, 35, 40] if code == CODE_1965 else [25, 30, 35, 40, 45, 50]
    k = _grade_key(fck, allowed)
    return CRACK_TENSION_DIRECT[k]


def permissible_concrete_bending_compression(fck: float) -> float:
    k = _grade_key(fck, sorted(WSM_CONCRETE_BENDING_COMPRESSION))
    return WSM_CONCRETE_BENDING_COMPRESSION[k]


def permissible_steel_tension_wsm(code: str, fy: float, member_thickness_mm: float | None = None, liquid_face: bool = True) -> float:
    hysd = fy > 250.0
    if code == CODE_2009:
        return 130.0 if hysd else 115.0
    if code == CODE_1965:
        if not hysd:
            if not liquid_face and member_thickness_mm is not None and member_thickness_mm >= 225:
                return 125.0
            return 115.0
        if not liquid_face and member_thickness_mm is not None and member_thickness_mm >= 225:
            return 190.0
        return 150.0
    raise ValueError("WSM steel stress is only defined for the 1965/2009 branches.")


def modular_ratio_wsm(fck: float) -> float:
    sigma_cbc = permissible_concrete_bending_compression(fck)
    return 280.0 / (3.0 * sigma_cbc)


def wall_min_ratio_per_face(code: str, method: str, thickness_mm: float, fy: float) -> float:
    """Return required steel ratio per face based on gross b*D for one direction."""
    if code == CODE_2021:
        # Frozen visible workbook basis: 0.36% surface-zone ratio. For D<500 each face controls D/2.
        if thickness_mm < 500:
            return 0.0036 / 2.0
        return 0.0036 * 250.0 / thickness_mm
    if code == CODE_2009:
        # Full clause 8.1.1 value (0.35% surface zone); <=15m reduction not invoked without visible plan dimension.
        if thickness_mm < 500:
            return 0.0035 / 2.0
        return 0.0035 * 250.0 / thickness_mm
    if code == CODE_1965:
        if thickness_mm <= 100:
            gross_ratio = 0.0030
        elif thickness_mm < 450:
            gross_ratio = 0.0030 - (thickness_mm - 100.0) * (0.0010 / 350.0)
        else:
            gross_ratio = 0.0020
        if fy > 250.0:
            gross_ratio *= 0.80
        # Two layers are required at >=225 mm; for this app, equal face allocation is used.
        return gross_ratio / 2.0 if thickness_mm >= 225.0 else gross_ratio
    raise ValueError(f"Unsupported code {code}")


def footing_min_ratio_per_face(code: str, method: str, average_thickness_mm: float, fy: float) -> float:
    # The visible footing minimum-steel line uses the average footing thickness and one surface zone.
    return wall_min_ratio_per_face(code, method, average_thickness_mm, fy)


def shear_strength_wsm_1965(fck: float) -> float:
    k = _grade_key(fck, sorted(SHEAR_CRACK_1965))
    return SHEAR_CRACK_1965[k]


def shear_strength_wsm_2009(pt_percent: float, fck: float) -> float:
    k = _grade_key(fck, sorted(SHEAR_2009_WSM))
    vals = SHEAR_2009_WSM[k]
    if pt_percent <= PT_POINTS_2009[0]:
        return vals[0]
    if pt_percent >= PT_POINTS_2009[-1]:
        return vals[-1]
    for i in range(len(PT_POINTS_2009)-1):
        x0, x1 = PT_POINTS_2009[i], PT_POINTS_2009[i+1]
        if x0 <= pt_percent <= x1:
            y0, y1 = vals[i], vals[i+1]
            return y0 + (pt_percent-x0)*(y1-y0)/(x1-x0)
    raise RuntimeError("Unable to interpolate IS 3370:2009 WSM shear table")
