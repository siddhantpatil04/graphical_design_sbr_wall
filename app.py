from __future__ import annotations

from copy import deepcopy
import pandas as pd
import streamlit as st

from engine import calculate, default_inputs, linked_wall_thickness_profile, recommend_safe_thickness
from models import RebarLayer, WallStationInput
from pdf_report import build_pdf
from excel_export import build_excel
from ui_theme import ADVANCED_UI_CSS
from ui_graphics import wall_water_advanced_svg, footing_advanced_svg, thickness_profile_advanced_svg
from ui_components import project_strip, fixed_parameters_panel, legend_panel, quick_help_panel, reinforcement_summary, sidebar_status

from code_basis import (
    CODE_OPTIONS, CODE_1965, CODE_2009, CODE_2021,
    METHOD_LSM, METHOD_WSM, normalise_method, profile,
)


APP_TITLE = "RCC Design — SBR Wall W1 / W1A"

_APPROVED_DEFAULTS = default_inputs()
FIXED_GAMMA_CONCRETE = float(_APPROVED_DEFAULTS.gamma_concrete_kn_m3)
FIXED_LOAD_FACTOR = float(_APPROVED_DEFAULTS.load_factor)
FIXED_MIN_STABILITY_FOS = float(_APPROVED_DEFAULTS.allowable_fos)
CRACK_WIDTH_OPTIONS = [0.10, 0.15, 0.20, 0.25]

st.set_page_config(
    page_title="SBR WALL W1 Design",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
:root { color-scheme: dark; }
html, body, [class*="css"] { font-family: "Segoe UI", Arial, sans-serif; }
.stApp { background: #0e1117; color: #f3f4f6; }
.block-container {
    padding-top: 2.0rem;
    padding-bottom: 3rem;
    max-width: 1480px;
}
[data-testid="stSidebar"] {
    background: #24252e;
    border-right: 1px solid #343640;
}
[data-testid="stSidebar"] > div:first-child { padding-top: 1.0rem; }
[data-testid="stSidebar"] .block-container { padding-top: 0.8rem; }

h1, h2, h3 { color: #ffffff; letter-spacing: -0.02em; }
h1 { font-size: 2.15rem !important; margin-bottom: .2rem !important; }
h2 { font-size: 1.72rem !important; margin-top: 1.2rem !important; }
h3 { font-size: 1.15rem !important; }
p, label, .stCaption { color: #d1d5db; }

/* Inputs */
[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: #262730 !important;
    color: #ffffff !important;
    border-color: #30323c !important;
    border-radius: 7px !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus {
    border-color: #ff4b4b !important;
    box-shadow: 0 0 0 1px #ff4b4b !important;
}
[data-testid="stWidgetLabel"] p {
    color: #ffffff !important;
    font-size: .82rem !important;
    font-weight: 600 !important;
}

/* Buttons */
.stButton > button[kind="primary"],
.stDownloadButton > button[kind="primary"] {
    background: #ff4b4b !important;
    border: 1px solid #ff4b4b !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-radius: 7px !important;
}
.stButton > button[kind="primary"]:hover,
.stDownloadButton > button[kind="primary"]:hover {
    background: #ff6262 !important;
    border-color: #ff6262 !important;
}
.stButton > button:not([kind="primary"]),
.stDownloadButton > button:not([kind="primary"]) {
    background: #171a21;
    border: 1px solid #343840;
    color: #f3f4f6;
    border-radius: 7px;
}

/* Recommended SAFE-design apply action */
.st-key-apply_safe_design button {
    background: #15803d !important;
    border: 1px solid #22c55e !important;
    color: #ffffff !important;
    font-weight: 750 !important;
}
.st-key-apply_safe_design button:hover {
    background: #16a34a !important;
    border-color: #4ade80 !important;
}

/* Expanders and tables */
[data-testid="stExpander"] {
    border: 1px solid #343840 !important;
    background: #11151c !important;
    border-radius: 8px !important;
}
[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border: 1px solid #2f333d;
    border-radius: 8px;
    overflow: hidden;
}

/* Metrics / cards */
[data-testid="stMetric"] {
    background: #11151c;
    border: 1px solid #343840;
    border-radius: 8px;
    padding: .85rem .95rem;
    min-height: 96px;
}
[data-testid="stMetricLabel"] { color: #e5e7eb; }
[data-testid="stMetricValue"] { color: #ffffff; }

/* Tabs */
button[data-baseweb="tab"] { color: #d1d5db !important; font-weight: 600; }
button[data-baseweb="tab"][aria-selected="true"] { color: #ff5a5f !important; }
[data-baseweb="tab-highlight"] { background-color: #ff4b4b !important; }

.section-divider {
    height: 1px;
    background: #343840;
    margin: 1.65rem 0 1.55rem 0;
}
.section-kicker {
    color: #ffffff;
    font-size: 1.72rem;
    line-height: 1.2;
    font-weight: 750;
    margin: .25rem 0 1.05rem 0;
}
.app-subtitle {
    color: #8f969f;
    font-size: .80rem;
    margin-top: -.25rem;
    margin-bottom: 1.25rem;
}
.status-safe {
    background: #123d2c;
    border: 1px solid #1f6849;
    color: #55e69d;
    padding: .82rem 1rem;
    border-radius: 7px;
    font-weight: 650;
    margin-bottom: .85rem;
}
.status-unsafe {
    background: #431c22;
    border: 1px solid #74303a;
    color: #ff8289;
    padding: .82rem 1rem;
    border-radius: 7px;
    font-weight: 650;
    margin-bottom: .85rem;
}
.status-stale {
    background: #453411;
    border: 1px solid #795d1d;
    color: #f7cb62;
    padding: .82rem 1rem;
    border-radius: 7px;
    font-weight: 600;
    margin-bottom: .85rem;
}
.sidebar-title {
    color: #ffffff;
    font-weight: 750;
    font-size: 1.0rem;
    margin: .25rem 0 .65rem 0;
}
.sidebar-note {
    color: #a8aeb8;
    font-size: .74rem;
    line-height: 1.45;
}
.code-ok {
    background: #123d2c;
    border: 1px solid #1f6849;
    color: #69e6a8;
    padding: .55rem .65rem;
    border-radius: 7px;
    font-size: .76rem;
}
.code-warn {
    background: #453411;
    border: 1px solid #795d1d;
    color: #f7cb62;
    padding: .55rem .65rem;
    border-radius: 7px;
    font-size: .76rem;
}
.small-note { color: #9299a4; font-size: .78rem; }

/* Draftsman-friendly graphical input view */
.input-mode-bar {
    background: #11151c; border: 1px solid #343840; border-radius: 10px;
    padding: .75rem .9rem; margin: .2rem 0 1rem 0;
}
.diagram-card {
    background: linear-gradient(180deg, #121720 0%, #0f131a 100%);
    border: 1px solid #343840; border-radius: 12px; padding: .9rem 1rem;
    min-height: 100%;
}
.diagram-title { color:#ffffff; font-size:1rem; font-weight:750; margin-bottom:.15rem; }
.diagram-subtitle { color:#8f969f; font-size:.76rem; margin-bottom:.65rem; line-height:1.35; }
.draftsman-tip {
    background:#102a3b; border:1px solid #1e5875; color:#b8e7ff;
    padding:.7rem .85rem; border-radius:8px; font-size:.80rem; line-height:1.45;
    margin:.25rem 0 .9rem 0;
}
.graphical-input-panel {
    background:#11151c; border:1px solid #2e333d; border-radius:10px; padding:.75rem .85rem;
}
.lock-pill {
    display:inline-block; color:#c9d0d8; background:#1a2028; border:1px solid #343840;
    border-radius:999px; padding:.2rem .55rem; margin:.15rem .15rem .15rem 0; font-size:.72rem;
}
</style>
""",
    unsafe_allow_html=True,
)


st.markdown(ADVANCED_UI_CSS, unsafe_allow_html=True)

# ---------- helpers ----------
def section_title(number: int, text: str) -> None:
    st.markdown(f'<div class="section-kicker">{number}. {text}</div>', unsafe_allow_html=True)


def divider() -> None:
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)


def crack_display(crack: dict) -> str:
    value = crack.get("wcr_mm")
    return "N/A — stress control" if value is None else f"{float(value):.2f} mm"


def check_by_name(result, name: str):
    return next((c for c in result.checks if c.name == name), None)


def edit_layers(title: str, layers: list[RebarLayer], key: str) -> list[RebarLayer]:
    st.markdown(f"**{title}**")
    df = pd.DataFrame(
        [{"Layer": i + 1, "Dia (mm)": l.dia_mm, "Spacing (mm)": l.spacing_mm} for i, l in enumerate(layers)]
    )
    edited = st.data_editor(
        df,
        hide_index=True,
        use_container_width=True,
        key=key,
        disabled=["Layer"],
        num_rows="fixed",
    )
    return [RebarLayer(float(r["Dia (mm)"]), float(r["Spacing (mm)"])) for r in edited.to_dict("records")]


def _diagram_shell(title: str, subtitle: str, svg: str) -> str:
    return f"""
<div class="diagram-card">
  <div class="diagram-title">{title}</div>
  <div class="diagram-subtitle">{subtitle}</div>
  {svg}
</div>
"""


def wall_geometry_svg(inp) -> str:
    """Simple not-to-scale wall / water / raft section for draftsman input guidance."""
    liquid_depth = max(inp.water_top_rl_m - (inp.raft_top_rl_m + inp.footing_total_thickness_m - inp.footing_edge_thickness_m) + inp.freeboard_m, 0.0)
    return f"""
<svg viewBox="0 0 720 455" width="100%" role="img" aria-label="Wall and water level input schematic">
  <defs>
    <linearGradient id="waterFill" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#3b82f6" stop-opacity="0.48"/>
      <stop offset="100%" stop-color="#1d4ed8" stop-opacity="0.22"/>
    </linearGradient>
    <linearGradient id="concreteFill" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#6b7280"/><stop offset="100%" stop-color="#9ca3af"/>
    </linearGradient>
    <marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L8,4 L0,8 z" fill="#d1d5db"/>
    </marker>
  </defs>
  <rect x="20" y="16" width="680" height="420" rx="12" fill="#0b0f15" stroke="#29303a"/>
  <text x="42" y="45" fill="#9ca3af" font-size="15">SECTION — NOT TO SCALE</text>

  <!-- water retained on the inner face -->
  <polygon points="70,155 365,155 337,365 70,365" fill="url(#waterFill)"/>
  <path d="M70 155 Q90 147 110 155 T150 155 T190 155 T230 155 T270 155 T310 155 T350 155" fill="none" stroke="#60a5fa" stroke-width="4"/>
  <text x="112" y="190" fill="#bfdbfe" font-size="20" font-weight="700">LIQUID</text>
  <text x="112" y="214" fill="#93c5fd" font-size="14">Depth ~ {liquid_depth:.2f} m</text>

  <!-- tapered wall -->
  <polygon points="365,78 414,78 448,365 337,365" fill="url(#concreteFill)" stroke="#d1d5db" stroke-width="2"/>
  <text x="383" y="230" fill="#111827" font-size="18" font-weight="800" transform="rotate(90 383,230)">RCC WALL W1</text>

  <!-- footing / raft -->
  <rect x="190" y="365" width="390" height="42" rx="2" fill="#7b8491" stroke="#d1d5db" stroke-width="2"/>
  <text x="322" y="392" fill="#111827" font-size="17" font-weight="800">WALL FOOTING / RAFT</text>

  <!-- level lines -->
  <line x1="470" y1="78" x2="650" y2="78" stroke="#f87171" stroke-width="2" stroke-dasharray="6 5"/>
  <circle cx="483" cy="65" r="13" fill="#ff4b4b"/><text x="483" y="70" text-anchor="middle" fill="white" font-size="13" font-weight="800">1</text>
  <text x="503" y="70" fill="#ffffff" font-size="14">Top of Wall RL = {inp.wall_top_rl_m:.3f} m</text>

  <line x1="438" y1="155" x2="650" y2="155" stroke="#60a5fa" stroke-width="2" stroke-dasharray="6 5"/>
  <circle cx="483" cy="142" r="13" fill="#2563eb"/><text x="483" y="147" text-anchor="middle" fill="white" font-size="13" font-weight="800">2</text>
  <text x="503" y="147" fill="#ffffff" font-size="14">Top Water RL = {inp.water_top_rl_m:.3f} m</text>

  <line x1="448" y1="365" x2="650" y2="365" stroke="#fbbf24" stroke-width="2" stroke-dasharray="6 5"/>
  <circle cx="483" cy="352" r="13" fill="#d97706"/><text x="483" y="357" text-anchor="middle" fill="white" font-size="13" font-weight="800">3</text>
  <text x="503" y="357" fill="#ffffff" font-size="14">Side-wall bottom</text>

  <line x1="448" y1="407" x2="650" y2="407" stroke="#34d399" stroke-width="2" stroke-dasharray="6 5"/>
  <circle cx="483" cy="394" r="13" fill="#059669"/><text x="483" y="399" text-anchor="middle" fill="white" font-size="13" font-weight="800">4</text>
  <text x="503" y="399" fill="#ffffff" font-size="14">Top of Raft RL = {inp.raft_top_rl_m:.3f} m</text>

  <text x="75" y="425" fill="#8f969f" font-size="13">Enter the RL values beside the matching numbered callouts.</text>
</svg>
"""


def footing_svg(inp) -> str:
    toe = float(inp.toe_projection_m)
    heel = float(inp.heel_projection_m)
    wall = max(float(inp.wall_stations[-1].provided_thickness_mm) / 1000.0, 0.05)
    total = max(toe + heel + wall, 0.1)
    x0, width = 70.0, 570.0
    toe_px = width * toe / total
    wall_px = max(width * wall / total, 42.0)
    # keep the graphic readable if the wall is visually widened by the minimum pixel width
    wall_x = x0 + toe_px
    wall_center = wall_x + wall_px / 2.0
    return f"""
<svg viewBox="0 0 720 390" width="100%" role="img" aria-label="Footing heel and toe projection schematic">
  <defs>
    <marker id="a2" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L8,4 L0,8 z" fill="#d1d5db"/>
    </marker>
  </defs>
  <rect x="20" y="16" width="680" height="350" rx="12" fill="#0b0f15" stroke="#29303a"/>
  <text x="42" y="45" fill="#9ca3af" font-size="15">FOOTING SECTION — NOT TO SCALE</text>

  <rect x="70" y="245" width="570" height="70" fill="#7b8491" stroke="#d1d5db" stroke-width="2"/>
  <polygon points="{wall_x:.1f},90 {wall_x+wall_px:.1f},90 {wall_x+wall_px+18:.1f},245 {wall_x-18:.1f},245" fill="#9ca3af" stroke="#e5e7eb" stroke-width="2"/>
  <text x="{wall_center:.1f}" y="166" text-anchor="middle" fill="#111827" font-size="18" font-weight="800" transform="rotate(90 {wall_center:.1f},166)">W1 WALL</text>

  <line x1="72" y1="222" x2="{wall_x-4:.1f}" y2="222" stroke="#60a5fa" stroke-width="2" marker-start="url(#a2)" marker-end="url(#a2)"/>
  <circle cx="120" cy="196" r="13" fill="#2563eb"/><text x="120" y="201" text-anchor="middle" fill="white" font-size="13" font-weight="800">1</text>
  <text x="143" y="201" fill="#ffffff" font-size="15" font-weight="700">TOE = {toe:.2f} m</text>

  <line x1="{wall_x+wall_px+4:.1f}" y1="222" x2="638" y2="222" stroke="#34d399" stroke-width="2" marker-start="url(#a2)" marker-end="url(#a2)"/>
  <circle cx="520" cy="196" r="13" fill="#059669"/><text x="520" y="201" text-anchor="middle" fill="white" font-size="13" font-weight="800">2</text>
  <text x="543" y="201" fill="#ffffff" font-size="15" font-weight="700">HEEL = {heel:.2f} m</text>

  <line x1="660" y1="245" x2="660" y2="315" stroke="#fbbf24" stroke-width="2" marker-start="url(#a2)" marker-end="url(#a2)"/>
  <circle cx="644" cy="278" r="13" fill="#d97706"/><text x="644" y="283" text-anchor="middle" fill="white" font-size="13" font-weight="800">3</text>
  <text x="430" y="338" fill="#ffffff" font-size="14">Thickness = {inp.footing_total_thickness_m*1000:.0f} mm</text>

  </svg>
"""


def thickness_profile_svg(stations: list[WallStationInput]) -> str:
    values = [float(s.provided_thickness_mm) for s in stations]
    mn, mx = min(values), max(values)
    spread = max(mx - mn, 1.0)
    y_top, y_bottom = 50.0, 435.0
    n = max(len(stations) - 1, 1)
    center = 330.0
    left_points, right_points = [], []
    labels = []
    for idx, (s, t) in enumerate(zip(stations, values)):
        y = y_top + (y_bottom - y_top) * idx / n
        half = 34.0 + 72.0 * (t - mn) / spread
        left_points.append(f"{center-half:.1f},{y:.1f}")
        right_points.append(f"{center+half:.1f},{y:.1f}")
        labels.append(
            f'<line x1="{center+half+8:.1f}" y1="{y:.1f}" x2="545" y2="{y:.1f}" stroke="#374151" stroke-width="1"/>'
            f'<text x="555" y="{y+5:.1f}" fill="#d1d5db" font-size="12">{s.label}: {t:.0f} mm</text>'
        )
    polygon = " ".join(left_points + list(reversed(right_points)))
    return f"""
<svg viewBox="0 0 720 485" width="100%" role="img" aria-label="Linked wall thickness profile">
  <rect x="20" y="16" width="680" height="450" rx="12" fill="#0b0f15" stroke="#29303a"/>
  <text x="42" y="43" fill="#9ca3af" font-size="15">LINKED WALL THICKNESS PROFILE</text>
  <polygon points="{polygon}" fill="#7b8491" stroke="#e5e7eb" stroke-width="2"/>
  <line x1="330" y1="48" x2="330" y2="440" stroke="#d1d5db" stroke-width="1" stroke-dasharray="5 5" opacity=".45"/>
  {''.join(labels)}
  <text x="48" y="452" fill="#8f969f" font-size="13">Edit any one station; the same change is applied to every station.</text>
</svg>
"""


def _station_from_row(old: WallStationInput, row: dict, thickness_mm: float | None = None) -> WallStationInput:
    return WallStationInput(
        label=old.label,
        fraction=old.fraction,
        special_height_m=old.special_height_m,
        provided_thickness_mm=float(old.provided_thickness_mm if thickness_mm is None else thickness_mm),
        vertical_main=RebarLayer(float(row["Vertical Main Dia (mm)"]), float(row["Vertical Main Spacing (mm)"])),
        vertical_extra=RebarLayer(float(row["Vertical Extra Dia (mm)"]), float(row["Vertical Extra Spacing (mm)"])),
        horizontal_main=RebarLayer(float(row["Horizontal Dia (mm)"]), float(row["Horizontal Spacing (mm)"])),
        horizontal_corner=RebarLayer(float(row["Corner Dia (mm)"]), float(row["Corner Spacing (mm)"])),
    )


def _wall_rebar_editor(inp, key: str) -> None:
    rows = []
    for s in inp.wall_stations:
        rows.append({
            "Station": s.label,
            "Vertical Main Dia (mm)": s.vertical_main.dia_mm,
            "Vertical Main Spacing (mm)": s.vertical_main.spacing_mm,
            "Vertical Extra Dia (mm)": s.vertical_extra.dia_mm,
            "Vertical Extra Spacing (mm)": s.vertical_extra.spacing_mm,
            "Horizontal Dia (mm)": s.horizontal_main.dia_mm,
            "Horizontal Spacing (mm)": s.horizontal_main.spacing_mm,
            "Corner Dia (mm)": s.horizontal_corner.dia_mm,
            "Corner Spacing (mm)": s.horizontal_corner.spacing_mm,
        })
    edited = st.data_editor(
        pd.DataFrame(rows), hide_index=True, use_container_width=True, key=key,
        disabled=["Station"], num_rows="fixed",
    )
    recs = edited.to_dict("records")
    inp.wall_stations = [_station_from_row(old, row) for old, row in zip(inp.wall_stations, recs)]


def _render_fixed_parameters(inp) -> None:
    with st.expander("🔒 Fixed Design Parameters", expanded=False):
        st.caption("Read-only approved values. These are shown only for checking and cannot be edited.")
        f1, f2, f3 = st.columns(3)
        f1.metric("Unit Weight of RCC", f"{inp.gamma_concrete_kn_m3:.2f} kN/m³")
        f2.metric("Load Factor", f"{inp.load_factor:.2f}")
        f3.metric("Minimum Stability FOS", f"{inp.allowable_fos:.2f}")
        st.markdown(
            '<span class="lock-pill">🔒 RCC unit weight</span>'
            '<span class="lock-pill">🔒 load factor</span>'
            '<span class="lock-pill">🔒 stability FOS</span>',
            unsafe_allow_html=True,
        )
        if inp.design_method == METHOD_WSM:
            st.caption("The locked load factor remains the approved project parameter; WSM calculations use service-load factor 1.00 by the selected method.")


# ---------- state ----------
if "defaults" not in st.session_state:
    st.session_state.defaults = default_inputs()
if "last_result" not in st.session_state:
    st.session_state.last_result = None
    st.session_state.last_fp = None
    st.session_state.recommendation = None
if "thickness_widget_version" not in st.session_state:
    st.session_state.thickness_widget_version = 0
if "safe_apply_notice" not in st.session_state:
    st.session_state.safe_apply_notice = None
if "linked_profile_notice" not in st.session_state:
    st.session_state.linked_profile_notice = None
if "input_widget_version" not in st.session_state:
    st.session_state.input_widget_version = 0
if "last_input_view" not in st.session_state:
    st.session_state.last_input_view = "🖼 Graphical Input"


def apply_recommended_safe_design() -> None:
    """Apply an already-verified thickness-only SAFE recommendation to live inputs."""
    rec = st.session_state.get("recommendation")
    if not rec or not rec.get("found") or rec.get("result") is None:
        st.session_state.safe_apply_notice = "No valid SAFE recommendation is available to apply."
        return

    rr = rec["result"]
    applied = deepcopy(rr.inputs)

    # The optimiser freezes every non-thickness input. Replacing defaults with the
    # recommended input object therefore preserves the user's current loads, materials,
    # reinforcement, levels, code and project data while applying only the thicknesses.
    st.session_state.defaults = applied

    # Force the two thickness widgets that can be programmatically changed to rebuild
    # from the newly applied values on the next rerun.
    st.session_state.thickness_widget_version += 1

    # The recommendation result was calculated using exactly these applied inputs, so it
    # can safely become the current result immediately; no second manual Run is required.
    st.session_state.last_result = rr
    st.session_state.last_fp = applied.fingerprint()
    st.session_state.recommendation = None
    st.session_state.safe_apply_notice = (
        "Recommended SAFE thicknesses applied successfully. "
        "All non-thickness inputs were kept unchanged."
    )


base = deepcopy(st.session_state.defaults)
# These are approved fixed design parameters. They are intentionally not editable in the UI.
base.gamma_concrete_kn_m3 = FIXED_GAMMA_CONCRETE
base.load_factor = FIXED_LOAD_FACTOR
base.allowable_fos = FIXED_MIN_STABILITY_FOS


# ---------- sidebar ----------
with st.sidebar:
    st.markdown('<div class="sidebar-title">📋 Project Information</div>', unsafe_allow_html=True)
    p = base.project
    p.structure = st.text_input("Structure Name", p.structure)
    p.document_no = st.text_input("Document Number", p.document_no)
    p.client = st.text_input("Client", p.client)
    p.project = st.text_input("Project", p.project)
    p.contractor = st.text_input("Contractor", p.contractor)
    p.consultant = st.text_input("Consultant", p.consultant)
    p.structural_consultant = st.text_input("Structural Consultant", p.structural_consultant)

    with st.expander("Preparation / approval details", expanded=False):
        p.prepared_by = st.text_input("Prepared By", p.prepared_by)
        p.checked_by = st.text_input("Checked By", p.checked_by)
        p.approved_by = st.text_input("Approved By", p.approved_by)
    p.revision = st.text_input("Revision", p.revision)

    st.divider()
    st.markdown('<div class="sidebar-title">📐 Design Standard</div>', unsafe_allow_html=True)
    design_code = st.selectbox(
        "IS Code",
        CODE_OPTIONS,
        index=CODE_OPTIONS.index(base.design_code) if base.design_code in CODE_OPTIONS else 0,
        key="design_code_selector",
        help="The selected code changes the implemented design methodology and code-specific checks.",
    )
    if design_code == CODE_2009:
        design_method = st.selectbox(
            "Design Method",
            [METHOD_LSM, METHOD_WSM],
            index=0 if base.design_method != METHOD_WSM else 1,
            key="design_method_selector",
            help="IS 3370:2009 permits either limit-state or working-stress design.",
        )
    elif design_code == CODE_1965:
        design_method = METHOD_WSM
        st.caption("Design method: Working Stress Design (legacy code basis)")
    else:
        design_method = METHOD_LSM
        st.caption("Design method: Limit State Design")

    design_method = normalise_method(design_code, design_method)
    base.design_code = design_code
    base.design_method = design_method
    basis = profile(design_code, design_method)
    st.markdown(
        f'<div class="code-ok">✓ {design_code} — {design_method} enabled</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Selected code basis", expanded=False):
        for note in basis.notes:
            st.markdown(f'<div class="sidebar-note">• {note}</div>', unsafe_allow_html=True)

    with st.expander("Scope & basis", expanded=False):
        st.markdown(
            """
<div class="sidebar-note">
<b>Application scope:</b> visible WALL W1 / W1A and visible wall-footing calculations only.<br><br>
<b>Hidden workbook content:</b> reference/dependency only where a visible calculation requires it.<br><br>
<b>QD-003:</b> intentionally ignored as instructed.<br><br>
<b>Shear:</b> code-specific. Limit-state branches use IS 456:2000 Table 19; legacy WSM branches use the applicable IS 3370 permissible-shear basis.<br><br>
<b>Code selector:</b> 1965, 2009 and 2021 are calculation-active; 2009 also permits selection of LSM or WSM.
</div>
""",
            unsafe_allow_html=True,
        )


# ---------- header ----------
st.title(f"🏗️ {APP_TITLE}")
st.markdown(
    f'<div class="app-subtitle">IS 456:2000 | {design_code} | {design_method} | Visible workbook scope | Inside Liquid Pressure</div>',
    unsafe_allow_html=True,
)

project_strip(base.project)

st.markdown('<div class="input-mode-bar"><b>Input Mode</b> — Graphical mode is intended for draftsmen and occasional users; Detailed mode exposes the full engineering form.</div>', unsafe_allow_html=True)
input_view = st.radio(
    "Choose how you want to enter the design data",
    ["🖼 Graphical Input", "📋 Detailed Input"],
    index=0 if st.session_state.last_input_view == "🖼 Graphical Input" else 1,
    horizontal=True,
    key="input_view_selector",
    help="Both views use the same underlying input data. Switching view does not change the design.",
)
if input_view != st.session_state.last_input_view:
    st.session_state.last_input_view = input_view
    st.session_state.input_widget_version += 1
ui_v = st.session_state.input_widget_version


if input_view == "🖼 Graphical Input":
    st.markdown(
        '<div class="adv-section-header"><div class="adv-section-title">GRAPHICAL INPUT — WALL, WATER & FOOTING</div><div class="adv-help">ⓘ Match numbered inputs to the same number on the drawings</div></div>',
        unsafe_allow_html=True,
    )

    main_left, main_right = st.columns([2.15, 1.0], gap="medium")

    # ======================== LEFT SIDE: PRIMARY DRAFTSMAN INPUTS ========================
    with main_left:
        # --- Wall / liquid section ---
        with st.container(border=True):
            input_col, graphic_col = st.columns([0.78, 1.62], gap="medium")
            with input_col:
                st.markdown('<div class="adv-panel-title">Wall & Water Inputs</div>', unsafe_allow_html=True)
                base.wall_top_rl_m = st.number_input(
                    "① Top of Wall RL (m)", value=float(base.wall_top_rl_m), step=0.05, format="%.3f", key=f"ag_wall_top_{ui_v}",
                    help="Reduced level at the top of the RCC wall.",
                )
                base.water_top_rl_m = st.number_input(
                    "② Top Water Level RL (m)", value=float(base.water_top_rl_m), step=0.05, format="%.3f", key=f"ag_water_top_{ui_v}",
                    help="Highest retained liquid level used for this design input.",
                )
                base.raft_top_rl_m = st.number_input(
                    "③ Top of Raft RL (m)", value=float(base.raft_top_rl_m), step=0.05, format="%.3f", key=f"ag_raft_top_{ui_v}",
                    help="Reduced level at the top surface of the raft/footing reference.",
                )
                crack_index = min(range(len(CRACK_WIDTH_OPTIONS)), key=lambda idx: abs(CRACK_WIDTH_OPTIONS[idx] - float(base.crack_limit_mm)))
                base.crack_limit_mm = st.selectbox(
                    "Design Crack Width", CRACK_WIDTH_OPTIONS, index=crack_index, key=f"ag_crack_{ui_v}",
                    format_func=lambda value: f"{value:.2f} mm",
                )
                base.wall_cover_mm = st.number_input(
                    "④ Wall Clear Cover (mm)", min_value=10.0, value=float(base.wall_cover_mm), step=5.0, key=f"ag_wall_cover_{ui_v}",
                )
                with st.expander("More wall geometry", expanded=False):
                    base.freeboard_m = st.number_input("Freeboard Addition (m)", min_value=0.0, value=float(base.freeboard_m), step=0.05, key=f"ag_freeboard_{ui_v}")
                    base.cutoff_height_m = st.number_input("Special Cut-off Station Height (m)", min_value=0.0, value=float(base.cutoff_height_m), step=0.05, key=f"ag_cutoff_{ui_v}")
                    base.wall_taper_height_m = st.number_input("Wall Taper Height at Footing (m)", min_value=0.0, value=float(base.wall_taper_height_m), step=0.10, key=f"ag_taper_{ui_v}")
            with graphic_col:
                st.markdown(wall_water_advanced_svg(base), unsafe_allow_html=True)

        # --- Material / site inputs kept compact, because they are not dimensions on the section ---
        with st.expander("Material & site design inputs", expanded=True):
            if design_code == CODE_1965:
                concrete_options = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
            elif design_code == CODE_2009:
                concrete_options = [25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
            else:
                concrete_options = [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
            if float(base.fck_mpa) not in concrete_options:
                base.fck_mpa = 30.0
            steel_options = [250.0, 415.0, 500.0, 550.0]
            if float(base.fy_mpa) not in steel_options:
                steel_options = sorted(steel_options + [float(base.fy_mpa)])
            mi1, mi2, mi3, mi4 = st.columns(4)
            base.fck_mpa = mi1.selectbox("Concrete Grade", concrete_options, index=concrete_options.index(float(base.fck_mpa)), key=f"ag_fck_{ui_v}", format_func=lambda x: f"M{x:g}")
            base.fy_mpa = mi2.selectbox("Steel Grade", steel_options, index=steel_options.index(float(base.fy_mpa)), key=f"ag_fy_{ui_v}", format_func=lambda x: f"Fe{x:g}")
            base.sbc_kn_m2 = mi3.number_input("Safe Bearing Capacity (kN/m²)", min_value=1.0, value=float(base.sbc_kn_m2), step=5.0, key=f"ag_sbc_{ui_v}")
            base.gamma_liquid_kn_m3 = mi4.number_input("Unit Weight of Liquid (kN/m³)", min_value=0.1, value=float(base.gamma_liquid_kn_m3), step=0.5, key=f"ag_gamma_liquid_{ui_v}")

        crack_incompatible = design_method == METHOD_LSM and base.crack_limit_mm > 0.20 + 1e-9
        if crack_incompatible:
            st.error(
                f"{base.crack_limit_mm:.2f} mm is available in the requested dropdown, but the implemented {design_code} "
                "Limit State basis does not permit a crack-width limit above 0.20 mm. Select 0.20 mm or a stricter value to run."
            )
        elif design_method == METHOD_WSM:
            st.caption(
                f"Selected crack-width criterion: {base.crack_limit_mm:.2f} mm. In WSM, acceptance remains governed by the applicable permissible-stress / resistance-to-cracking checks."
            )
        if design_code == CODE_1965 and base.fy_mpa > 415:
            st.caption("1965 branch: modern Fe500/Fe550 is checked using the implemented legacy HYSD permissible-stress cap.")

        # --- Footing geometry section ---
        st.markdown('<div class="adv-panel-title" style="margin-top:.55rem">⑥ Footing Geometry (Section)</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(footing_advanced_svg(base), unsafe_allow_html=True)
            fg1, fg2, fg3, fg4, fg5 = st.columns(5)
            base.toe_projection_m = fg1.number_input("⑥ Toe Projection (m)", min_value=0.10, value=float(base.toe_projection_m), step=0.05, key=f"ag_toe_{ui_v}")
            base.heel_projection_m = fg2.number_input("⑦ Heel Projection (m)", min_value=0.10, value=float(base.heel_projection_m), step=0.05, key=f"ag_heel_{ui_v}")
            base.footing_edge_thickness_m = fg3.number_input("⑧ Footing Edge (m)", min_value=0.05, value=float(base.footing_edge_thickness_m), step=0.025, key=f"ag_foot_edge_{ui_v}")
            base.footing_total_thickness_m = fg4.number_input("⑨ Total Footing (m)", min_value=0.05, value=float(base.footing_total_thickness_m), step=0.025, key=f"ag_foot_total_{st.session_state.thickness_widget_version}_{ui_v}")
            base.footing_cover_mm = fg5.number_input("⑩ Footing Cover (mm)", min_value=10.0, value=float(base.footing_cover_mm), step=5.0, key=f"ag_foot_cover_{ui_v}")

        # --- Locked parameters / legend / help like the visual mockup ---
        fp, lg, qh = st.columns([1.35, .68, .90], gap="small")
        with fp:
            with st.container(border=True):
                fixed_parameters_panel(base)
        with lg:
            with st.container(border=True):
                legend_panel()
        with qh:
            with st.container(border=True):
                quick_help_panel()

    # ======================== RIGHT SIDE: PROFILE + REINFORCEMENT ========================
    with main_right:
        st.markdown('<div class="adv-panel-title">⑤ Linked Wall Thickness Profile</div>', unsafe_allow_html=True)
        with st.container(border=True):
            rows = [{"Station": s.label, "Thickness (mm)": float(s.provided_thickness_mm)} for s in base.wall_stations]
            profile_key = f"ag_profile_{st.session_state.thickness_widget_version}_{ui_v}"
            edited_profile = st.data_editor(
                pd.DataFrame(rows), hide_index=True, use_container_width=True, key=profile_key, disabled=["Station"], num_rows="fixed",
                column_config={"Thickness (mm)": st.column_config.NumberColumn("Thickness (mm)", min_value=max(50.0,float(base.wall_cover_mm)+1.0), step=1.0, format="%.0f")},
                height=420,
            )
            recs = edited_profile.to_dict("records")
            baseline = [float(s.provided_thickness_mm) for s in base.wall_stations]
            edited_thks = [float(r["Thickness (mm)"]) for r in recs]
            diffs = [i for i,(old,new) in enumerate(zip(baseline,edited_thks)) if abs(old-new)>1e-9]
            if diffs:
                editor_state = st.session_state.get(profile_key,{})
                edited_rows_state = editor_state.get("edited_rows",{}) if isinstance(editor_state,dict) else {}
                changed = [int(i) for i,changes in edited_rows_state.items() if isinstance(changes,dict) and "Thickness (mm)" in changes]
                edited_index = changed[-1] if changed else diffs[-1]
                linked_values = linked_wall_thickness_profile(base.wall_stations, edited_index, edited_thks[edited_index])
                delta = linked_values[edited_index] - baseline[edited_index]
                for s,linked in zip(base.wall_stations,linked_values):
                    s.provided_thickness_mm=float(linked)
                st.session_state.defaults=deepcopy(base)
                st.session_state.thickness_widget_version += 1
                st.session_state.recommendation=None
                st.session_state.linked_profile_notice=(f"Linked profile updated from {base.wall_stations[edited_index].label}: {delta:+.0f} mm applied to every wall station.")
                st.rerun()
            st.markdown(thickness_profile_advanced_svg(base.wall_stations), unsafe_allow_html=True)
            st.caption("Change any one thickness value and the whole approved profile shifts by the same Δ.")

        if st.session_state.linked_profile_notice:
            st.info(st.session_state.linked_profile_notice)
            st.session_state.linked_profile_notice = None

        st.markdown('<div class="adv-panel-title" style="margin-top:.65rem">⑪ Reinforcement Summary</div>', unsafe_allow_html=True)
        with st.container(border=True):
            reinforcement_summary(base)
            st.caption("Summary only — click the advanced expanders below to edit reinforcement.")

        with st.expander("Advanced wall reinforcement — engineer / checker", expanded=False):
            _wall_rebar_editor(base, key=f"ag_wall_rebar_{ui_v}")
        with st.expander("Advanced footing reinforcement — engineer / checker", expanded=False):
            c1,c2=st.columns(2)
            with c1: base.footing_top_layers=edit_layers("Top reinforcement",base.footing_top_layers,f"ag_ftop_{ui_v}")
            with c2: base.footing_bottom_layers=edit_layers("Bottom reinforcement",base.footing_bottom_layers,f"ag_fbot_{ui_v}")
            c1,c2=st.columns(2)
            with c1: base.footing_distribution_top=edit_layers("Top distribution reinforcement",base.footing_distribution_top,f"ag_fdtop_{ui_v}")
            with c2: base.footing_distribution_bottom=edit_layers("Bottom distribution reinforcement",base.footing_distribution_bottom,f"ag_fdbot_{ui_v}")

else:
    # ---------- Detailed engineering input view ----------
    st.markdown('<div class="draftsman-tip"><b>Detailed Input View:</b> use this when an engineer/checker wants the traditional full form and reinforcement schedule. It controls the same data as Graphical Input View.</div>', unsafe_allow_html=True)

    section_title(1, "Wall Geometry & Levels")
    c1, c2, c3 = st.columns(3)
    base.wall_top_rl_m = c1.number_input("Top Level of Wall RL (m)", value=float(base.wall_top_rl_m), step=0.05, format="%.3f", key=f"d_wall_top_{ui_v}")
    base.water_top_rl_m = c2.number_input("Top Level of Water RL (m)", value=float(base.water_top_rl_m), step=0.05, format="%.3f", key=f"d_water_top_{ui_v}")
    base.raft_top_rl_m = c3.number_input("Top Level of Raft RL (m)", value=float(base.raft_top_rl_m), step=0.05, format="%.3f", key=f"d_raft_top_{ui_v}")
    c1, c2, c3 = st.columns(3)
    base.freeboard_m = c1.number_input("Freeboard Addition (m)", min_value=0.0, value=float(base.freeboard_m), step=0.05, key=f"d_freeboard_{ui_v}")
    base.cutoff_height_m = c2.number_input("Special Cut-off Station Height (m)", min_value=0.0, value=float(base.cutoff_height_m), step=0.05, key=f"d_cutoff_{ui_v}")
    base.wall_taper_height_m = c3.number_input("Wall Taper Height at Footing (m)", min_value=0.0, value=float(base.wall_taper_height_m), step=0.10, key=f"d_taper_{ui_v}")

    divider()
    section_title(2, "Material Properties & Design Limits")
    c1, c2, c3 = st.columns(3)
    if design_code == CODE_1965:
        concrete_options = [15.0, 20.0, 25.0, 30.0, 35.0, 40.0]
    elif design_code == CODE_2009:
        concrete_options = [25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
    else:
        concrete_options = [20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0]
    if float(base.fck_mpa) not in concrete_options:
        base.fck_mpa = 30.0
    base.fck_mpa = c1.selectbox("Concrete Grade fck (MPa)", concrete_options, index=concrete_options.index(float(base.fck_mpa)), key=f"d_fck_{ui_v}")
    steel_options = [250.0, 415.0, 500.0, 550.0]
    if float(base.fy_mpa) not in steel_options:
        steel_options = sorted(steel_options + [float(base.fy_mpa)])
    base.fy_mpa = c2.selectbox("Steel Grade fy (MPa)", steel_options, index=steel_options.index(float(base.fy_mpa)), key=f"d_fy_{ui_v}")
    base.wall_cover_mm = c3.number_input("Wall Clear Cover (mm)", min_value=10.0, value=float(base.wall_cover_mm), step=5.0, key=f"d_wall_cover_{ui_v}")
    c1, c2, c3 = st.columns(3)
    base.sbc_kn_m2 = c1.number_input("Safe Bearing Capacity (kN/m²)", min_value=1.0, value=float(base.sbc_kn_m2), step=5.0, key=f"d_sbc_{ui_v}")
    base.gamma_liquid_kn_m3 = c2.number_input("Unit Weight of Liquid (kN/m³)", min_value=0.1, value=float(base.gamma_liquid_kn_m3), step=0.5, key=f"d_gamma_liquid_{ui_v}")
    crack_index = min(range(len(CRACK_WIDTH_OPTIONS)), key=lambda idx: abs(CRACK_WIDTH_OPTIONS[idx] - float(base.crack_limit_mm)))
    base.crack_limit_mm = c3.selectbox("Allowable Crack Width (mm)", CRACK_WIDTH_OPTIONS, index=crack_index, key=f"d_crack_{ui_v}", format_func=lambda value: f"{value:.2f} mm")
    crack_incompatible = design_method == METHOD_LSM and base.crack_limit_mm > 0.20 + 1e-9
    if crack_incompatible:
        st.error(f"{base.crack_limit_mm:.2f} mm is not compatible with the implemented {design_code} Limit State crack-width limit. Select 0.20 mm or a stricter value.")
    elif design_method == METHOD_WSM:
        st.caption(f"Crack-width selection retained: {base.crack_limit_mm:.2f} mm. WSM acceptance is governed by permissible-stress / resistance-to-cracking checks.")
    _render_fixed_parameters(base)

    divider()
    section_title(3, "Wall Thickness & Reinforcement")
    st.markdown('<div class="small-note">The wall thickness schedule is linked. Editing one station applies the same thickness change (Δ) to every station.</div>', unsafe_allow_html=True)
    with st.expander("Advanced wall thickness & reinforcement schedule", expanded=False):
        rows = []
        for s in base.wall_stations:
            rows.append({
                "Station": s.label, "Thickness (mm)": s.provided_thickness_mm,
                "Vertical Main Dia (mm)": s.vertical_main.dia_mm, "Vertical Main Spacing (mm)": s.vertical_main.spacing_mm,
                "Vertical Extra Dia (mm)": s.vertical_extra.dia_mm, "Vertical Extra Spacing (mm)": s.vertical_extra.spacing_mm,
                "Horizontal Dia (mm)": s.horizontal_main.dia_mm, "Horizontal Spacing (mm)": s.horizontal_main.spacing_mm,
                "Corner Dia (mm)": s.horizontal_corner.dia_mm, "Corner Spacing (mm)": s.horizontal_corner.spacing_mm,
            })
        editor_key = f"d_wall_schedule_{st.session_state.thickness_widget_version}_{ui_v}"
        edited = st.data_editor(
            pd.DataFrame(rows), hide_index=True, use_container_width=True, key=editor_key, disabled=["Station"], num_rows="fixed",
            column_config={"Thickness (mm)": st.column_config.NumberColumn("Thickness (mm)", min_value=max(50.0, float(base.wall_cover_mm)+1.0), step=1.0, format="%.0f")},
        )
        recs = edited.to_dict("records")
        baseline = [float(s.provided_thickness_mm) for s in base.wall_stations]
        edited_thks = [float(r["Thickness (mm)"]) for r in recs]
        diffs = [i for i,(old,new) in enumerate(zip(baseline, edited_thks)) if abs(old-new)>1e-9]
        if diffs:
            editor_state = st.session_state.get(editor_key, {})
            edited_rows_state = editor_state.get("edited_rows", {}) if isinstance(editor_state, dict) else {}
            changed = [int(i) for i, changes in edited_rows_state.items() if isinstance(changes, dict) and "Thickness (mm)" in changes]
            edited_index = changed[-1] if changed else diffs[-1]
            linked_values = linked_wall_thickness_profile(base.wall_stations, edited_index, edited_thks[edited_index])
            delta = linked_values[edited_index] - baseline[edited_index]
            base.wall_stations = [_station_from_row(old, row, linked) for old,row,linked in zip(base.wall_stations,recs,linked_values)]
            st.session_state.defaults = deepcopy(base)
            st.session_state.thickness_widget_version += 1
            st.session_state.recommendation = None
            st.session_state.linked_profile_notice = f"Linked wall profile updated from {base.wall_stations[edited_index].label}: {delta:+.0f} mm applied to every station."
            st.rerun()
        base.wall_stations = [_station_from_row(old,row,float(row["Thickness (mm)"])) for old,row in zip(base.wall_stations,recs)]
    if st.session_state.linked_profile_notice:
        st.info(st.session_state.linked_profile_notice)
        st.session_state.linked_profile_notice = None
    bottom_input = base.wall_stations[-1]
    q1,q2,q3,q4 = st.columns(4)
    q1.metric("Bottom Wall Thickness", f"{bottom_input.provided_thickness_mm:.0f} mm")
    q2.metric("Bottom Vertical Main", f"Ø{bottom_input.vertical_main.dia_mm:g} @ {bottom_input.vertical_main.spacing_mm:g} mm")
    q3.metric("Bottom Vertical Extra", f"Ø{bottom_input.vertical_extra.dia_mm:g} @ {bottom_input.vertical_extra.spacing_mm:g} mm" if bottom_input.vertical_extra.dia_mm > 0 else "None")
    q4.metric("Bottom Horizontal", f"Ø{bottom_input.horizontal_main.dia_mm:g} @ {bottom_input.horizontal_main.spacing_mm:g} mm")

    divider()
    section_title(4, "Wall Footing")
    c1,c2,c3,c4,c5 = st.columns(5)
    base.toe_projection_m = c1.number_input("Toe Projection (m)", min_value=0.10, value=float(base.toe_projection_m), step=0.05, key=f"d_toe_{ui_v}")
    base.heel_projection_m = c2.number_input("Heel Projection (m)", min_value=0.10, value=float(base.heel_projection_m), step=0.05, key=f"d_heel_{ui_v}")
    base.footing_edge_thickness_m = c3.number_input("Footing Edge Thickness (m)", min_value=0.05, value=float(base.footing_edge_thickness_m), step=0.025, key=f"d_foot_edge_{ui_v}")
    base.footing_total_thickness_m = c4.number_input("Total Footing Thickness (m)", min_value=0.05, value=float(base.footing_total_thickness_m), step=0.025, key=f"d_foot_total_{st.session_state.thickness_widget_version}_{ui_v}")
    base.footing_cover_mm = c5.number_input("Footing Clear Cover (mm)", min_value=10.0, value=float(base.footing_cover_mm), step=5.0, key=f"d_foot_cover_{ui_v}")
    with st.expander("Advanced footing reinforcement inputs", expanded=False):
        c1,c2 = st.columns(2)
        with c1: base.footing_top_layers = edit_layers("Top reinforcement", base.footing_top_layers, f"d_ftop_{ui_v}")
        with c2: base.footing_bottom_layers = edit_layers("Bottom reinforcement", base.footing_bottom_layers, f"d_fbot_{ui_v}")
        c1,c2 = st.columns(2)
        with c1: base.footing_distribution_top = edit_layers("Top distribution reinforcement", base.footing_distribution_top, f"d_fdtop_{ui_v}")
        with c2: base.footing_distribution_bottom = edit_layers("Bottom distribution reinforcement", base.footing_distribution_bottom, f"d_fdbot_{ui_v}")

# Persist the current input view into the shared canonical state. This is what keeps
# Graphical Input and Detailed Input synchronized when the user switches views.
st.session_state.defaults = deepcopy(base)

# ---------- manual run ----------
# The code and method are part of DesignInputs, so any selector change invalidates the previous result.
current_fp = base.fingerprint()

# Any editable-input or code/method change invalidates a previously generated SAFE recommendation.
if st.session_state.last_fp is not None and st.session_state.last_fp != current_fp:
    st.session_state.recommendation = None

st.markdown("<div style='height:.65rem'></div>", unsafe_allow_html=True)
c_run, c_restore = st.columns([5, 1])
run_clicked = c_run.button(
    "▶  RUN DESIGN CALCULATION",
    key="advanced_run_button",
    type="primary",
    use_container_width=True,
    disabled=crack_incompatible,
    help="Resolve the crack-width/code incompatibility above before running." if crack_incompatible else None,
)
if run_clicked:
    try:
        st.session_state.last_result = calculate(base)
        st.session_state.last_fp = current_fp
        st.session_state.recommendation = None
    except Exception as exc:
        st.session_state.last_result = None
        st.session_state.last_fp = None
        st.error(f"Calculation stopped: {exc}")

if c_restore.button("Restore Defaults", use_container_width=True):
    st.session_state.clear()
    st.rerun()

if st.session_state.safe_apply_notice:
    notice = st.session_state.safe_apply_notice
    st.session_state.safe_apply_notice = None
    if notice.startswith("Recommended SAFE"):
        st.success(notice)
    else:
        st.warning(notice)

fresh = st.session_state.last_result is not None and st.session_state.last_fp == current_fp
with st.sidebar:
    sidebar_status(fresh, st.session_state.last_result)
if st.session_state.last_result is not None and not fresh:
    st.markdown(
        '<div class="status-stale">Inputs or the design-code selection changed after the previous run. The previous result is invalidated. Click <b>Run Design Calculation</b> for the current inputs.</div>',
        unsafe_allow_html=True,
    )


divider()
section_title(5, "Design Results")

if not fresh:
    st.markdown(
        '<div class="small-note">No current calculation result. Set the inputs above and click <b>Run Design Calculation</b>.</div>',
        unsafe_allow_html=True,
    )
else:
    r = st.session_state.last_result
    if r.overall_status == "SAFE":
        st.markdown(
            '<div class="status-safe">Overall status: SAFE for all checks currently implemented in this visible-scope application.</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-unsafe">Overall status: UNSAFE — one or more implemented mandatory checks fail.</div>',
            unsafe_allow_html=True,
        )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Overall", "✅ SAFE" if r.overall_status == "SAFE" else "❌ UNSAFE")
    c2.metric("Liquid Depth", f"{r.wall['liquid_depth_m']:.3f} m")
    c3.metric("Governing Wall Moment", f"{r.wall['bottom_factored_moment_knm_m']:.2f} kNm/m")
    c4.metric("Wall Serviceability", crack_display(r.wall["crack"]))
    c5.metric("Footing FOS", f"{r.footing['fos']:.3f}")

    tabs = st.tabs(["Summary", "W1 — Wall", "Footing", "Serviceability", "Checks", "Calculations", "Reports"])

    with tabs[0]:
        sc1, sc2, sc3, sc4 = st.columns(4)
        sc1.metric("Wall Status", r.wall_status)
        sc2.metric("Footing Status", r.footing_status)
        sc3.metric("Footing pmax", f"{r.footing['pmax_kn_m2']:.2f} kN/m²")
        sc4.metric("Footing Serviceability", crack_display(r.footing["crack"]))
        if r.warnings:
            st.markdown("**Scope / limitations**")
            for warning in r.warnings:
                st.write("-", warning)

    with tabs[1]:
        wall_df = pd.DataFrame([s.__dict__ for s in r.wall_stations]).rename(columns={
            "service_moment_knm_m": "service_moment_kNm_m",
            "factored_moment_knm_m": "design_moment_kNm_m",
        })
        st.dataframe(wall_df, use_container_width=True, hide_index=True)
        with st.expander("Wall calculation summary", expanded=False):
            st.write({k: v for k, v in r.wall.items() if k != "crack"})

    with tabs[2]:
        footing_summary = {
            "FOS": r.footing["fos"],
            "Eccentricity (m)": r.footing["eccentricity_abs_m"],
            "pmax (kN/m²)": r.footing["pmax_kn_m2"],
            "pmin (kN/m²)": r.footing["pmin_kn_m2"],
            "Heel moment (kNm/m)": r.footing["heel_moment_knm_m"],
            "Toe moment (kNm/m)": r.footing["toe_moment_knm_m"],
            "Required footing thickness (mm)": r.footing["required_thickness_mm"],
            "Provided footing thickness (mm)": r.footing["provided_thickness_mm"],
        }
        st.dataframe(
            pd.DataFrame([{"Parameter": k, "Value": v} for k, v in footing_summary.items()]),
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Detailed footing result", expanded=False):
            st.write(r.footing)

    with tabs[3]:
        if r.inputs.design_method == METHOD_LSM:
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Wall crack width", crack_display(r.wall["crack"]))
            s2.metric("Allowable crack width", f"{r.inputs.crack_limit_mm:.2f} mm")
            s3.metric("Footing crack width", crack_display(r.footing["crack"]))
            wall_shear = check_by_name(r, "Wall shear")
            s4.metric("Wall shear status", wall_shear.status if wall_shear else r.wall_status)
            with st.expander("Wall crack calculation", expanded=False):
                st.write(r.wall["crack"])
            with st.expander("Footing crack calculation", expanded=False):
                st.write(r.footing["crack"])
        else:
            wc = r.wall["crack"]
            fc = r.footing["crack"]
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Wall concrete tension", f"{wc.get('concrete_tension_mpa', 0):.3f} / {wc.get('concrete_tension_allow_mpa', 0):.3f} MPa")
            s2.metric("Wall steel stress", f"{wc.get('fs_mpa', 0):.1f} / {wc.get('steel_allow_mpa', 0):.1f} MPa")
            s3.metric("Footing concrete tension", f"{fc.get('concrete_tension_mpa', 0):.3f} / {fc.get('concrete_tension_allow_mpa', 0):.3f} MPa")
            s4.metric("Footing steel stress", f"{fc.get('fs_mpa', 0):.1f} / {fc.get('steel_allow_mpa', 0):.1f} MPa")
            st.caption("Working Stress Design uses resistance-to-cracking and permissible-stress checks; an Annex-B calculated crack width is not used for this branch.")
            with st.expander("Wall WSM serviceability calculation", expanded=False):
                st.write(wc)
            with st.expander("Footing WSM serviceability calculation", expanded=False):
                st.write(fc)

    with tabs[4]:
        checks_df = pd.DataFrame([c.__dict__ for c in r.checks])
        st.dataframe(checks_df, use_container_width=True, hide_index=True)
        failed = r.failed_checks()
        if failed:
            st.error("Failed mandatory checks: " + ", ".join(c.name for c in failed))
        else:
            st.success("All implemented mandatory checks pass.")

    with tabs[5]:
        st.dataframe(pd.DataFrame([t.__dict__ for t in r.formula_trace]), use_container_width=True, hide_index=True)
        with st.expander("Approved source reconciliation", expanded=False):
            for note in r.reconciliation_notes:
                st.write("-", note)

    with tabs[6]:
        pdf = build_pdf(r, st.session_state.recommendation)
        xlsx = build_excel(r, st.session_state.recommendation)
        c1, c2 = st.columns(2)
        c1.download_button(
            "📄 Download Submission PDF",
            data=pdf,
            file_name="SBR_WALL_W1_Design_Calculation.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        c2.download_button(
            "📊 Download Calculation Excel",
            data=xlsx,
            file_name="SBR_WALL_W1_Calculation_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    # ---------- SAFE design module ----------
    if r.overall_status == "UNSAFE":
        divider()
        section_title(6, "Recommended SAFE Design")
        st.markdown(
            '<div class="status-unsafe">The current input set is UNSAFE. The recommendation routine changes thickness only and freezes reinforcement, loads, materials and all non-thickness geometry.</div>',
            unsafe_allow_html=True,
        )

        if st.button("🛠  Recommend SAFE Thickness", type="primary", use_container_width=True):
            with st.spinner("Searching thickness-only combinations..."):
                st.session_state.recommendation = recommend_safe_thickness(base)
            st.rerun()

        rec = st.session_state.recommendation
        if rec:
            if rec.get("found"):
                rr = rec["result"]
                st.success("A SAFE thickness-only solution was found for all implemented mandatory checks.")
                rc1, rc2, rc3 = st.columns(3)
                rc1.metric("Wall Profile Increase", f"+{rec['wall_increase_mm']:.0f} mm")
                rc2.metric("Footing Thickness Increase", f"+{rec['footing_increase_mm']:.0f} mm")
                rc3.metric("Recommended Footing Thickness", f"{rr.inputs.footing_total_thickness_m * 1000:.0f} mm")
                st.markdown("**Recommended wall thickness profile (mm)**")
                st.write([s.provided_thickness_mm for s in rr.inputs.wall_stations])
                if rec.get("governing_failed_checks"):
                    st.markdown("**Governing failed checks from the current design**")
                    for item in rec["governing_failed_checks"]:
                        st.write("-", item)
                st.caption("All reinforcement, loads, materials and non-thickness geometry remain frozen during the search.")

                st.markdown("<div style='height:.35rem'></div>", unsafe_allow_html=True)
                st.button(
                    "✅  Apply Recommended SAFE Design",
                    key="apply_safe_design",
                    use_container_width=True,
                    on_click=apply_recommended_safe_design,
                    help=(
                        "Apply the recommended wall and footing thicknesses to the live inputs. "
                        "Reinforcement, materials, loads, levels, project data and the selected code remain unchanged."
                    ),
                )
            else:
                st.error(rec.get("message", "No valid thickness-only solution was found within the permitted range."))
