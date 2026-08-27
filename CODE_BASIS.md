# Design-code implementation basis

This file documents only the code provisions implemented for the **visible WALL W1 / W1A and visible wall-footing scope**. It is not a substitute for the standards.

## IS 3370:2021

**Method implemented:** Limit State Design only.

Implemented for the visible W1 scope:
- limit-state flexural section sizing and reinforcement using the reconciled workbook basis;
- calculated crack-width check with maximum selected crack limit not exceeding 0.20 mm;
- Annex-B serviceability prerequisites used by this engine: steel stress <= 0.60 fy and concrete stress <= 0.40 fck;
- visible-workbook minimum reinforcement basis retained as 0.36% of each surface zone (0.18% of gross section per face for D < 500 mm);
- shear strength from IS 456:2000 Table 19 for the LSM branch.

Working Stress Design is not offered under the 2021 selector.

## IS 3370:2009 Part 2

**Methods implemented:**
- Limit State Design; and
- Working Stress Design.

The uploaded `IS 3370 (Part 2):2009` states that either LSM or WSM may be used. The app therefore exposes a second **Design Method** selector when 2009 is chosen.

### 2009 - Limit State Design
- reconciled LSM wall/footing strength calculation;
- Annex-B calculated crack width;
- serviceability prerequisites: steel stress <= 0.80 fy and concrete stress <= 0.45 fck;
- Clause 8.1.1 minimum reinforcement: 0.35% of each surface zone for high-strength deformed bars;
- the optional reduction to 0.24% for tanks with no dimension above 15 m is **not invoked**, because that plan dimension is outside the visible W1 scope;
- shear uses IS 456:2000 Table 19.

### 2009 - Working Stress Design
- cracking resistance by permissible concrete bending tension from Table 1;
- cracked-section steel and concrete compression stress checks;
- high-strength deformed-bar permissible tensile stress of 130 N/mm2 for the implemented liquid-face bending/shear condition;
- permissible concrete shear stress interpolated from Table 3;
- Clause 8.1.1 minimum reinforcement as above;
- no Annex-B numerical crack width is reported for this WSM branch; serviceability is reported as stress control.

## IS 3370:1965 Part II

**Method implemented:** Working Stress Design.

Implemented for the visible W1 scope:
- resistance-to-cracking check using permissible concrete bending tension from the legacy table;
- cracked-section steel and concrete compression stress checks;
- legacy HYSD permissible stress caps (rather than modern fy-based allowable stress);
- legacy permissible cracking-shear table;
- Clause 7.1.1 minimum reinforcement: 0.30% gross section up to 100 mm, linearly reducing to 0.20% at 450 mm, then 0.20%; 20% reduction for high-yield deformed bars; two-face distribution for sections >= 225 mm;
- modern Fe500/Fe550 selections are treated as HYSD for the legacy permissible-stress cap because the 1965 code does not provide modern grade-specific Fe500/Fe550 WSM allowables.

## Scope safeguards common to all branches

- Only visible WALL W1 / W1A and visible wall-footing calculations are application scope.
- Hidden workbook rows/cells are reference/dependency material only when a visible calculation requires them.
- QD-003 / `WALL W1!M200 = #REF!` remains intentionally ignored.
- The visible footing workbook contains serviceability for the top/heel face only; a separate bottom/toe serviceability block is not added from hidden content.
- The SAFE-design optimiser changes **thickness only** and always reruns the currently selected code/method.

## Crack-width selector behaviour

The web UI offers 0.10, 0.15, 0.20 and 0.25 mm as project criteria. The selected value is carried through the result, formula trace and reports. For implemented LSM branches, a criterion above the verified 0.20 mm maximum is explicitly rejected before calculation. For WSM branches, the selected value is retained for project/report traceability but does not replace the legacy permissible-stress / resistance-to-cracking acceptance method.
