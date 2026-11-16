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
- **Parity:** must match exactly - model constants (A0, BETA, FP, VCC, TAU_VIEW1,
  F1_MIN/F1_MAX, BODE_X1/BODE_X2), LoopSim (DT, MASK, NOISE, half-sample correction,
  rec/trim), phase ranges/defaults (0-360 @0, 95-270 @120), slider ranges/steps/
  defaults, banner thresholds and copy, plot titles/ticks/units, palette and stage-px
  sizes. Enforced by `tests/test_parity.py` for everything except layout/drawing.
- **Testable logic lives in pure module-level functions**, same names in both files
  (`view1_status`/`view1Status`, `view2_status`, `view1_ratio`, `linked_phase`,
  `time_unit`, `phase_label`, `bode_freqs`, formatters). Put new numbers/wording there, not inside
  `App.refresh` / `update()`, or the tests can't see them.
- **View 1 signal frequency is 1 Hz - 300 kHz** so the linked phase reaches 0 deg
  (pole alone is 5.7 deg at 100 Hz). View 1's Bode axis is therefore 1 Hz - 1 MHz
  with every other decade labelled (`xlabels`); view 2 keeps 100 Hz - 1 MHz.

## Tests (`py -m unittest discover -s tests -v`, stdlib unittest)
- `test_model.py` - Python physics vs textbook formulas, incl. LoopSim steady-state
  gain vs |A/(1+AB)| (1 % tolerance; catches a lost half-sample correction).
- `test_parity.py` - runs the HTML's script via `tests/js_harness.mjs` (stub DOM)
  under node or deno; **skipped if neither is on PATH**. Sim traces are compared
  with NOISE = 0 and a square wave (no sin(), so bit-exact).
- `test_html_portable.py` - static: one self-contained file, no network, no syntax
  newer than Safari 14 (no static class fields, `?.`, `??`, CSS `inset`). Browser:
  headless Chrome/Edge `--dump-dom` from `file://`, both views (`#2` = view 2),
  checks the `#err` bar is empty and every canvas was drawn. Skipped with no browser.
- Headless Chrome often runs no animation frames before dumping, so the page draws
  its first frame synchronously (`frame(performance.now())` at the end of the
  script). Don't change that back to `requestAnimationFrame(frame)`.
- Not covered: pixel layout, Tk drawing, Safari/Firefox (not installed on the dev PC).

## Commands
- `Feedback Phase Sim.bat` — double-click launcher (no console window).
- `py feedback_phase_sim.py` — run with a console (use this to see tracebacks).
- `feedback_phase_sim.html` — open in a browser (`...html#2` starts in view 2). A JS
  error shows as a red bar at the top of the page (`window.onerror` -> `#err`).
- `py -m unittest discover -s tests -v` — run before every commit.

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
- **Phase slider title differs by view** (`phase_label`): "Phase lag" in view 1 (a lag
  imposed on the signal), "Feedback Phase Lag" in view 2 (lag of A*B at crossover = a
  different amplifier). The label block grows and the rail shrinks to fit the longer title.
- **Bode dots:** only the signal frequency gets a dot. The crossover (grey) and 180 deg
  (orange) are lines only, on purpose - dots there made those points look special.
- Loop model and why a pure delay is used for excess phase: see README.md "The model"
  and the constants at the top of `feedback_phase_sim.py`.

## README screenshots (`docs/*.png`, 1024x768)
- Taken with headless Chrome (`--headless=new --window-size=1024,768 --screenshot=`)
  from a **scratch copy** of the HTML with a few lines appended to the script: no-op
  `requestAnimationFrame`, set `S` (`setMode(2)`, `S.shape`, `S.ph[mode]`), `update()`,
  then `frame(last + 100)` x75 to fill view 2's traces. `--virtual-time-budget` alone
  leaves view 2 empty. Current shots: view 1 @150 deg; view 2 square @135 and @195.
- Retake them when the layout, palette or banner copy changes.

## Status
- Public on GitHub: https://github.com/electricyoshi/Feedback-Phase-Shift-Sim (main). MIT licensed (holder: electricyoshi).
- GitHub Pages is on (legacy build from `main` /), so every push to main redeploys
  https://electricyoshi.github.io/Feedback-Phase-Shift-Sim/feedback_phase_sim.html -
  the link students are given. A broken HTML on main is live within a minute or two.
