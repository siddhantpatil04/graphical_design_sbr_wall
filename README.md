# SBR - WALL W1 / W1A Streamlit Design Application

This application reproduces the **visible calculation scope** of the reconciled `SBR - WALL W1` workbook. Hidden rows/cells are not application modules; they are used only where a visible result required a dependency (principally crack width and the original shear lookup).

## Implemented scope

- Design data and visible W1/W1A levels
- Inside-liquid wall pressure distribution
- Wall required thickness and vertical reinforcement at all visible stations
- Visible horizontal distribution reinforcement schedule
- Wall shear
- Wall crack-width calculation
- Wall-footing stability, FOS, eccentricity, pmax and pmin
- Heel and toe slab moments
- Footing thickness and top/bottom reinforcement
- Footing heel/toe shear
- Visible top/heel footing crack-width calculation
- Manual Run Design button with stale-result invalidation
- Dark engineering dashboard interface aligned to the supplied UI reference
- Fully functional left-sidebar IS-code selector for IS 3370:1965, IS 3370:2009 and IS 3370:2021
- Thickness-only SAFE-design optimiser
- A4 PDF report and XLSX calculation report

## Important scope exclusions

- Hidden outside-soil-pressure modules and unrelated hidden calculations
- A separate bottom/toe footing crack-width check (not present in the visible workbook block)
- QD-003 / `WALL W1!M200 = #REF!`, intentionally ignored by instruction

## Design-code selector

The sidebar contains three functional code branches:

- **IS 3370:2021** -> Limit State Design.
- **IS 3370:2009** -> user may choose **Limit State Design** or **Working Stress Design**.
- **IS 3370:1965** -> Working Stress Design.

Changing the code or design method invalidates the previous result. The user must click **Run Design Calculation** again, ensuring that the screen and downloaded reports always correspond to the current code selection.

The **Recommended SAFE Design** module calls the same selected code/method engine at every trial and changes thickness only.

## Verified design basis

- The reconciled visible workbook remains the geometric/loading/calculation baseline.
- 2021 uses the limit-state branch and its serviceability limits.
- The uploaded IS 3370 (Part 2):2009 supports both LSM and WSM; both are implemented for this visible scope.
- IS 3370 (Part II):1965 is implemented on its legacy working-stress / resistance-to-cracking basis.
- LSM shear uses IS 456:2000 Table 19 interpolation; WSM shear uses the applicable legacy IS 3370 basis.
- See `CODE_BASIS.md` for the exact implemented provisions and scope limitations.

## Run on Windows

1. Extract the ZIP.
2. Open PowerShell in the extracted folder.
3. Create a virtual environment:
   `py -m venv .venv`
4. If PowerShell blocks activation, you can skip activation and call the environment Python directly.
5. Install dependencies:
   `.venv\Scripts\python.exe -m pip install -r requirements.txt`
6. Run:
   `.venv\Scripts\python.exe -m streamlit run app.py`

Alternative after activating the environment:

`python -m streamlit run app.py`

## Tests

`.venv\Scripts\python.exe -m pip install -r requirements-dev.txt`

`.venv\Scripts\python.exe -m pytest -q`

The test suite contains a deliberately UNSAFE case and verifies that the thickness-only optimiser can recover a SAFE implemented-check status without changing reinforcement, loads or material properties.

## Status wording

The application deliberately uses: **SAFE for all checks currently implemented in this application.** It does not claim that the complete structure has been checked outside the visible calculation scope.

## Apply Recommended SAFE Design

When the current design is UNSAFE, use **Recommend SAFE Thickness**. If a valid thickness-only solution is found, the app now shows **Apply Recommended SAFE Design**. Clicking it:

- applies the recommended station-wise wall thicknesses;
- applies the recommended total wall-footing thickness;
- keeps reinforcement, materials, loads, levels, code/method, project data and all other non-thickness inputs unchanged;
- promotes the already-verified recommendation result to the current live SAFE result, so a second manual Run is not required.


## August 2026 interface/report refinement

The current build also includes the following submission/UI refinements:

- **Unit Weight of RCC**, **Load Factor** and **Minimum Stability FOS** are fixed, read-only project design parameters shown under a collapsed **Fixed Design Parameters** expander.
- Allowable crack width is a dropdown limited to **0.10, 0.15, 0.20 and 0.25 mm**. A selected value that is incompatible with the active LSM code basis is clearly blocked rather than silently accepted; WSM retains the selection for reporting while serviceability remains stress-controlled.
- **Toe projection** and **heel projection** are independent inputs and feed the full footing equilibrium, pressure, heel/toe moment, shear, reinforcement, report and SAFE-design calculations.
- The wall thickness editor is a **linked profile**: editing any one station applies the same thickness delta to all stations, preserving the approved station-to-station profile exactly. All changed values are immediately visible.
- The submission PDF no longer contains a standalone Project Information section. Essential identification is carried in the compact header/footer.
- The PDF no longer prints the automatic thickness recommendation history. Once a recommendation is applied, only the final live design is reported.
- Vertical and horizontal wall reinforcement are shown as separate, clearly readable tables in the PDF check summary.
- The default submission PDF has been compressed from the earlier seven-page layout to **three A4 pages** without removing the formula trace or mandatory check information.

Current automated regression suite: **14 tests passing**, covering the three code editions/method branches, deliberately UNSAFE behaviour, thickness-only optimisation, asymmetric heel/toe geometry, crack-width selector compatibility, linked wall-thickness propagation, report generation and compact PDF content/page count.

## Draftsman-friendly graphical input mode

The default opening screen is now **🖼 Graphical Input**. A second **📋 Detailed Input** mode remains available for engineers/checkers.

Both modes use the **same `DesignInputs` object**. The graphical mode does not create a second or simplified calculation path. When the user switches views, the current values are persisted and the alternate view is rebuilt from those same values.

Graphical mode includes:

- a simple wall / retained-liquid / raft schematic with numbered RL callouts;
- a linked wall-thickness profile drawing that updates with the current thickness schedule;
- separate Toe and Heel footing callouts on a footing section;
- project material/design-limit inputs in a compact panel;
- locked Fixed Design Parameters;
- advanced wall and footing reinforcement controls collapsed under **engineer / checker use** expanders.

The graphical sketches are intentionally labelled **NOT TO SCALE**. They are input guides only; all engineering calculations continue to use the approved numerical engine.

### Linked thickness behavior in graphical mode

Each wall-station thickness is visibly editable. Editing any one station applies the same additive thickness change (Δ) to every wall station by calling the existing `linked_wall_thickness_profile()` engine helper. This preserves the approved profile shape. The previous design result and any previous SAFE recommendation are invalidated after the change.

### Recommended SAFE Design

The existing **Recommend SAFE Thickness** and **Apply Recommended SAFE Design** functions are retained. Applying a recommendation updates the graphical thickness profile and footing-thickness input as well as the detailed engineering view.
