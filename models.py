from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace
from typing import Any
import json
import hashlib


@dataclass
class RebarLayer:
    dia_mm: float
    spacing_mm: float

    def area_per_m(self) -> float:
        if self.dia_mm <= 0 or self.spacing_mm <= 0:
            return 0.0
        from math import pi
        return (pi * self.dia_mm**2 / 4.0) * 1000.0 / self.spacing_mm


@dataclass
class WallStationInput:
    label: str
    fraction: float | None
    provided_thickness_mm: float
    vertical_main: RebarLayer
    vertical_extra: RebarLayer
    horizontal_main: RebarLayer
    horizontal_corner: RebarLayer
    special_height_m: float | None = None


@dataclass
class ProjectInfo:
    project: str = ""
    client: str = ""
    structure: str = "SBR - WALL W1 / W1A"
    document_no: str = ""
    contractor: str = ""
    consultant: str = "CV Patil & Associates"
    structural_consultant: str = "CV Patil & Associates"
    prepared_by: str = ""
    checked_by: str = ""
    approved_by: str = ""
    revision: str = "R0"


@dataclass
class DesignInputs:
    # Material / code data
    fck_mpa: float = 30.0
    fy_mpa: float = 500.0
    sbc_kn_m2: float = 120.0
    gamma_liquid_kn_m3: float = 10.0
    gamma_concrete_kn_m3: float = 25.0
    crack_limit_mm: float = 0.20
    load_factor: float = 1.50
    allowable_fos: float = 1.55
    design_code: str = "IS 3370:2021"
    design_method: str = "Limit State Design"

    # Levels / wall geometry
    wall_top_rl_m: float = 1591.95
    water_top_rl_m: float = 1589.75
    raft_top_rl_m: float = 1585.45
    freeboard_m: float = 0.0
    wall_cover_mm: float = 45.0
    cutoff_height_m: float = 4.50
    wall_taper_height_m: float = 2.40

    # Footing geometry
    toe_projection_m: float = 1.65
    heel_projection_m: float = 1.65
    footing_edge_thickness_m: float = 0.20
    footing_total_thickness_m: float = 0.30
    footing_cover_mm: float = 50.0

    # Footing reinforcement
    footing_top_layers: list[RebarLayer] = field(default_factory=lambda: [
        RebarLayer(10, 125), RebarLayer(10, 125), RebarLayer(0, 280), RebarLayer(0, 440)
    ])
    footing_bottom_layers: list[RebarLayer] = field(default_factory=lambda: [
        RebarLayer(0, 140), RebarLayer(8, 125), RebarLayer(16, 125)
    ])
    footing_distribution_top: list[RebarLayer] = field(default_factory=lambda: [RebarLayer(10, 125)])
    footing_distribution_bottom: list[RebarLayer] = field(default_factory=lambda: [RebarLayer(10, 125)])

    # Wall station schedules
    wall_stations: list[WallStationInput] = field(default_factory=list)

    project: ProjectInfo = field(default_factory=ProjectInfo)

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class CheckResult:
    name: str
    status: str  # SAFE / UNSAFE / INFO / N/A
    demand: float | None = None
    capacity: float | None = None
    unit: str = ""
    note: str = ""
    mandatory: bool = True


@dataclass
class FormulaTrace:
    calculation: str
    formula: str
    substitution: str
    result: str
    source: str = ""


@dataclass
class WallStationResult:
    label: str
    height_m: float
    water_depth_m: float
    pressure_kn_m2: float
    service_moment_knm_m: float
    factored_moment_knm_m: float
    required_thickness_mm: float
    provided_thickness_mm: float
    effective_depth_mm: float
    ast_flexural_mm2_m: float
    ast_min_mm2_m: float
    ast_required_mm2_m: float
    ast_provided_mm2_m: float
    vertical_status: str
    horizontal_required_mm2_m: float
    horizontal_main_provided_mm2_m: float
    horizontal_total_provided_mm2_m: float
    horizontal_status: str


@dataclass
class DesignResult:
    inputs: DesignInputs
    overall_status: str
    wall_status: str
    footing_status: str
    wall_stations: list[WallStationResult]
    wall: dict[str, Any]
    footing: dict[str, Any]
    checks: list[CheckResult]
    formula_trace: list[FormulaTrace]
    warnings: list[str]
    reconciliation_notes: list[str]

    def failed_checks(self) -> list[CheckResult]:
        return [c for c in self.checks if c.mandatory and c.status == "UNSAFE"]


def replace_inputs(inputs: DesignInputs, **kwargs: Any) -> DesignInputs:
    return replace(inputs, **kwargs)
