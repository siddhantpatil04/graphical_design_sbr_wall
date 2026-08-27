# Approved Source Reconciliation Notes

1. Side-wall bottom RL linked to the visible raft RL.
2. Wall water-depth distribution derived from visible levels at every station.
3. `M200 = #REF!` intentionally ignored and excluded from the engine.
4. Wall effective depth based on the largest active tension-bar diameter.
5. Governing footing moment uses the maximum absolute heel/toe moment.
6. Footing top/bottom reinforcement demand is selected by moment sign.
7. Eccentricity is checked by magnitude and pmin must remain non-negative.
8. Separate top and bottom footing effective depths are used.
9. One visible crack-width limit input drives both wall and footing checks.
10. Scope locked to Inside Liquid Pressure.
11. Equality is accepted at capacity limits.
12. Required-steel values are live dependencies; stale manually copied results are not used.
13. LSM shear uses piecewise IS 456:2000 Table 19 interpolation; legacy WSM branches use the applicable IS 3370 permissible-shear table.
14. The visible footing geometry is generalized from the workbook's equal projections to independent toe and heel projections; the same equilibrium/load methodology is retained with the actual user-entered projection on each side.
15. Wall-thickness editing uses a linked additive delta at all stations so the approved thickness-profile shape is preserved exactly and no automatically changed thickness is hidden from the user.
16. Unit weight of RCC, load factor and minimum stability FOS are locked in the web UI at the existing approved project values.
17. PDF submission formatting was compacted; project identification moved to header/footer, optimisation history removed, and vertical/horizontal reinforcement separated in the check summary.

## Graphical Input View — draftsman usability update

- Added a new default **Graphical Input** mode while retaining the full **Detailed Input** mode.
- Both modes write to the same `DesignInputs` state; no duplicate or simplified engineering engine was created.
- Added a wall/liquid/raft section schematic with numbered RL callouts.
- Added a live linked wall-thickness silhouette and visible station-by-station thickness inputs.
- Added an independent toe/wall/heel footing schematic with numbered toe, heel and thickness callouts.
- Advanced wall and footing reinforcement controls are collapsed and labelled for engineer/checker use.
- View switching rebuilds widgets from the shared canonical input state so graphical and detailed values remain synchronized.
- Existing Run Design, multi-code selection, Recommended SAFE Thickness, Apply Recommended SAFE Design, PDF/Excel and stale-result invalidation remain intact.
