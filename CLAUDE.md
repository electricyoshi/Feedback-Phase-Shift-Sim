# Feedback Phase Shift Sim

Tier 1 teaching utility (EE3722 Module 4.2). Single-file tkinter GUI, stdlib only,
Python 3.8+. Intended for a **public** GitHub repo — keep it free of machine-specific
paths and personal details.

## Two implementations, kept in parallel
- `feedback_phase_sim.py` (tkinter) and `feedback_phase_sim.html` (vanilla JS, one
  file, no libraries, runs from `file://`) are **both maintained**. Any change to
  behaviour, model, copy, palette or layout goes into both in the same commit.
- The HTML mirrors the Python function for function (`LoopSim`, `plot` ~ `Plot.redraw`,
  `drawDiagram`, `drawPhasor`, `update` ~ `refresh`, `frame` ~ `tick`) to keep diffs
  comparable. It was written from the design handoff's `.dc.html`, not the bundled
  export (that is an opaque compressed bundle; don't edit or commit it).
- Known, accepted differences: browser draws dashes natively (no `dashed_line()`
  workaround needed); browser F11 is the browser's own full screen; sliders are native
  `<input type=range>` (log sliders step 0.005 decades vs continuous in Tk).
- **Parity:** must match exactly - model constants (A0, BETA, FP, VCC, TAU_VIEW1),
  LoopSim (DT, MASK, NOISE, half-sample correction, rec/trim), phase ranges/defaults
  (0-360 @0, 95-270 @120), slider ranges/steps/defaults, banner thresholds and copy,
  plot titles/ticks/units, palette and stage-px sizes.
- **Planned (not written yet): parity tests** in the test suite. Likely shape: run
  the HTML's pure functions (loop math, `LoopSim`, banner text, formatters) under
  node or a headless browser and compare against the Python on a grid of inputs;
  compare constants/strings by extraction. `LoopSim` noise uses `random`/`Math.random`,
  so it will need an injectable/seeded noise source (or NOISE=0) to compare traces.
  Optional later: screenshot comparison of the two UIs at 1024x768.

## Commands
- `Feedback Phase Sim.bat` — double-click launcher (no console window).
- `py feedback_phase_sim.py` — run with a console (use this to see tracebacks).
- `feedback_phase_sim.html` — open in a browser (F12 console for errors).

## Non-obvious decisions
- Launcher uses `start "" pyw ...`: without `start`, cmd waits on the GUI and leaves an
  empty console open. Falls back pyw → pythonw → py → python; the console fallbacks
  `pause` on error so students can read the message.
- No `.lnk` / `--install` (deviates from the Tier 1 bundle pattern on purpose): shortcuts
  embed absolute paths and don't survive a `git clone` onto another PC. `*.lnk` is
  gitignored.
- **Projector UI (design handoff, Nov 2026):** every size is in "stage px" on a
  1024x768 stage, times global `Z = min(win_w/1024, win_h/768)` (`zs()`, `bold(px)`).
  Root `<Configure>` (debounced) recomputes Z, resizes the named fonts in place
  (`rescale_fonts()`) and redraws. Fonts use negative = pixel sizes so DPI isn't
  applied twice. Palette/widths are final per the handoff; don't drift them.
- **All controls are canvas-drawn** (`ButtonBar`, `CheckBox`, `Slider`, `PhaseBar`):
  ttk can't do solid fills / 4 px borders on Windows and is too small on a projector.
  No ttk widgets remain.
- **Windows Tk dashes:** any dashed line wider than 1 px renders as dots. Wide dashed
  lines go through `dashed_line()` (stack of 1-px dashed lines); dashed traces always
  use the 1-px-stack path in `Plot._plot`; the phasor's dashed circle is solid arcs.
- **Subscripts:** UI strings use `V_{DIFF}` markup (uppercase subscripts, e.g. V_{IN},
  V_{OUT}, V_{FB}, V_{CC}). Unicode has no uppercase subscripts and Tk can't mix fonts
  in one text item, so `draw_rich()` / `draw_runs()` draw runs on canvases; `RichText`
  (read-only tk.Text) is only used for wrapped text in the "?" notes window. Plain-text
  spots (window title, Plot.put() "text" annotations) can't use markup.
- Loop model and why a pure delay is used for excess phase: see README.md "The model"
  and the constants at the top of `feedback_phase_sim.py`.

## Status
- Not yet pushed; GitHub remote (public) to be created later. MIT licensed (holder: electricyoshi).
