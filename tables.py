from __future__ import annotations

# IS 456:2000 Table 19 - design shear strength of concrete, tau_c (N/mm2).
# Source used to reconcile the workbook's hidden local interpolation:
# IS 456:2000, Table 19. Values are embedded so the deployed app has no network dependency.
PT_POINTS = [0.15, 0.25, 0.50, 0.75, 1.00, 1.25, 1.50, 1.75, 2.00, 2.25, 2.50, 2.75, 3.00]

SHEAR_TABLE = {
    15: [0.28, 0.35, 0.46, 0.54, 0.60, 0.64, 0.68, 0.71, 0.71, 0.71, 0.71, 0.71, 0.71],
    20: [0.28, 0.36, 0.48, 0.56, 0.62, 0.67, 0.72, 0.75, 0.79, 0.81, 0.82, 0.82, 0.82],
    25: [0.29, 0.36, 0.49, 0.57, 0.64, 0.70, 0.74, 0.78, 0.82, 0.85, 0.88, 0.90, 0.92],
    30: [0.29, 0.37, 0.50, 0.59, 0.66, 0.71, 0.76, 0.80, 0.84, 0.88, 0.91, 0.94, 0.96],
    35: [0.29, 0.37, 0.50, 0.59, 0.67, 0.73, 0.78, 0.82, 0.86, 0.90, 0.93, 0.96, 0.99],
    40: [0.30, 0.38, 0.51, 0.60, 0.68, 0.74, 0.79, 0.84, 0.88, 0.92, 0.95, 0.98, 1.01],
}


def concrete_grade_key(fck_mpa: float) -> int:
    # Table has explicit M15...M35 and M40-and-above. For intermediate grades,
    # use the next lower tabulated grade to remain conservative.
    if fck_mpa < 15:
        raise ValueError("IS 456 Table 19 is not implemented below M15.")
    if fck_mpa < 20:
        return 15
    if fck_mpa < 25:
        return 20
    if fck_mpa < 30:
        return 25
    if fck_mpa < 35:
        return 30
    if fck_mpa < 40:
        return 35
    return 40


def shear_strength_tau_c(pt_percent: float, fck_mpa: float) -> float:
    """Piecewise-linear interpolation of IS 456:2000 Table 19.

    At pt <= 0.15 use the table's <=0.15 value; above 3.0 use the 3.0-and-above value.
    """
    grade = concrete_grade_key(fck_mpa)
    vals = SHEAR_TABLE[grade]
    if pt_percent <= PT_POINTS[0]:
        return vals[0]
    if pt_percent >= PT_POINTS[-1]:
        return vals[-1]
    for i in range(len(PT_POINTS) - 1):
        x0, x1 = PT_POINTS[i], PT_POINTS[i + 1]
        if x0 <= pt_percent <= x1:
            y0, y1 = vals[i], vals[i + 1]
            return y0 + (pt_percent - x0) * (y1 - y0) / (x1 - x0)
    raise RuntimeError("Unable to interpolate shear table.")
