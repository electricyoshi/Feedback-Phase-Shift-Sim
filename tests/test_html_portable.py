"""Will feedback_phase_sim.html open on a student's PC, Mac or phone?

Static checks (always run): one self-contained file, nothing fetched, no
syntax that old Safari chokes on.  Browser checks (skipped when no Chrome,
Edge or Chromium is installed): load it from file:// in a real headless
browser and confirm the script ran in both views without an error, and
measure the portrait (phone) layout at real phone sizes.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
HTML = ROOT / "feedback_phase_sim.html"


def find_browser():
    names = ["chrome", "google-chrome", "chromium", "chromium-browser", "msedge", "microsoft-edge"]
    for n in names:
        if shutil.which(n):
            return shutil.which(n)
    paths = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    for env in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            paths += [os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
                      os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")]
    for p in paths:
        if os.path.exists(p):
            return p
    return None


class Static(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = HTML.read_bytes()
        cls.html = cls.raw.decode("utf-8")       # fails here if it isn't valid UTF-8

    def test_encoding_declared_and_no_bom(self):
        self.assertFalse(self.raw.startswith(b"\xef\xbb\xbf"))
        self.assertTrue(self.html.lstrip().lower().startswith("<!doctype html>"))
        self.assertIn('<meta charset="utf-8">', self.html[:1024])

    def test_nothing_is_loaded_from_anywhere(self):
        # works offline from a double-click: no external scripts, styles,
        # fonts, images, modules or network calls
        for pat in (r"<script[^>]+src=", r"<link\b", r"<img\b", r"<iframe\b", r"@import",
                    r"url\(", r"https?://", r"\bimport\s*\(", r"\bfetch\s*\(", r"XMLHttpRequest",
                    r'type="module"'):
            self.assertIsNone(re.search(pat, self.html, re.I), pat)

    def test_no_syntax_that_breaks_older_safari(self):
        # each of these is a hard syntax error (blank page) or a missing
        # feature on Safari / iPadOS a few years old
        script = "".join(re.findall(r"<script>(.*?)</script>", self.html, re.S))
        for pat, why in ((r"\bstatic\s+\w+\s*=", "static class fields (Safari < 14.1)"),
                         (r"\?\.", "optional chaining (Safari < 13.1)"),
                         (r"\?\?", "nullish coalescing (Safari < 13.1)"),
                         (r"#\w+\s*[=(;]", "private class members (Safari < 14.1)"),
                         (r"\.at\(", "Array.at (Safari < 15.4)"),
                         (r"\.replaceAll\(", "replaceAll (Safari < 13.1)"),
                         (r"structuredClone", "structuredClone (Safari < 15.4)")):
            self.assertIsNone(re.search(pat, script), why)
        self.assertNotIn("inset:", self.html, "CSS inset (Safari < 14.1)")

    def test_error_banner_comes_before_the_main_script(self):
        self.assertLess(self.html.index("window.onerror"), self.html.index("'use strict'"))


@unittest.skipUnless(find_browser(), "needs Chrome, Edge or Chromium installed")
class InBrowser(unittest.TestCase):
    def dump(self, fragment=""):
        with tempfile.TemporaryDirectory() as profile:
            r = subprocess.run(
                [find_browser(), "--headless=new", "--disable-gpu", "--no-first-run",
                 "--user-data-dir=" + profile, "--window-size=1024,768",
                 # Headless Chrome often runs no animation frames at all
                 # before dumping; the page draws its first frame
                 # synchronously at load, and that is what gets checked.
                 "--virtual-time-budget=2000", "--dump-dom", HTML.as_uri() + fragment],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertIn("</html>", r.stdout, r.stderr[-2000:])
        return r.stdout

    def check_no_error(self, dom):
        err = re.search(r'<div id="err" style="([^"]*)"[^>]*>(.*?)</div>', dom, re.S)
        self.assertIn("display:none", err.group(1).replace(" ", ""), err.group(2))
        self.assertEqual(err.group(2), "")

    def has(self, dom, text):
        self.assertTrue(text in dom, "not on the page: " + text)     # (keeps the DOM out of the log)

    def drawn(self, dom, canvas_id):
        # a canvas only gets a width attribute once something drew on it
        self.assertTrue(re.search(r'<canvas id="%s"[^>]*width="\d{3,}"' % canvas_id, dom),
                        "canvas %s was never drawn" % canvas_id)

    def test_view_1_runs_from_file_url(self):
        dom = self.dump()
        self.check_no_error(dom)
        self.has(dom, "|V<sub>DIFF</sub>| = 0.10 × |V<sub>IN</sub>|")
        self.has(dom, "Negative feedback: the difference shrinks")
        for c in ("cvD", "cvPA", "cvPB", "cvR1"):
            self.drawn(dom, c)

    def test_view_2_runs_from_file_url(self):
        dom = self.dump("#2")
        self.check_no_error(dom)
        self.has(dom, "Phase margin +60°")
        self.has(dom, "Gain margin +9.4 dB")
        for c in ("cvD", "cvPA", "cvPB", "cvR1", "cvR2"):
            self.drawn(dom, c)

    def dump_with(self, extra):
        # load a scratch copy of the page with `extra` appended after the main script
        with tempfile.TemporaryDirectory() as d:
            page = pathlib.Path(d) / "page.html"
            page.write_text(self.html_text().replace("</body>", extra + "</body>"), encoding="utf-8")
            r = subprocess.run(
                [find_browser(), "--headless=new", "--disable-gpu", "--no-first-run",
                 "--user-data-dir=" + str(pathlib.Path(d) / "profile"),
                 "--window-size=1024,768", "--virtual-time-budget=2000",
                 "--dump-dom", page.as_uri()],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        self.assertIn("</html>", r.stdout, r.stderr[-2000:])
        return r.stdout

    @staticmethod
    def html_text():
        return HTML.read_text(encoding="utf-8")

    def test_foreign_script_errors_do_not_show_the_error_bar(self):
        # Brave on iOS injects scripts; one threw and the browser reported it as
        # the sanitised cross-origin "Script error." at line 0.  That (and an
        # extension's own URL) must not put the error bar over a working page.
        dom = self.dump_with("<script>window.onerror('Script error.', '', 0, 0, null);"
                             "window.onerror('TypeError: x', 'chrome-extension://abc/inject.js', 12);"
                             "</script>")
        self.check_no_error(dom)

    def test_own_script_errors_still_show_the_error_bar(self):
        dom = self.dump_with("<script>null.boom();</script>")
        err = re.search(r'<div id="err" style="([^"]*)"[^>]*>(.*?)</div>', dom, re.S)
        self.assertIn("display:block", err.group(1).replace(" ", ""))
        self.assertIn("This page hit an error", err.group(2))


# Appended to a scratch copy of the page, after the main script.  Drives the
# page through its states and measures the layout, then posts the numbers to
# the parent frame (file:// frames are cross-origin, so no direct access).
PROBE = r"""
<script>
requestAnimationFrame = function () {};       // keep the states this script sets
(function () {
  var de = document.documentElement, vw = de.clientWidth, $ = function (id) { return document.getElementById(id); };
  var out = { portrait: de.classList.contains('portrait'), vw: vw, vh: innerHeight,
              transform: $('stage').style.transform, wide: [], textOverflow: [], stickGap: [],
              bannerH: [], canvases: {} };
  function check(tag) {
    // anything sticking out past the screen edge means sideways scrolling or a cut-off control
    var all = document.querySelectorAll('#stage *');
    for (var i = 0; i < all.length; i++) {
      var r = all[i].getBoundingClientRect();
      if (r.width && (r.left < -0.5 || r.right > vw + 0.5)) out.wide.push(tag + ' ' + (all[i].id || all[i].className || all[i].tagName));
    }
    ['b1', 'b2', 'b3', 'eq', 'tab1', 'tab2', 'phaseTitle', 'phaseSub', 'phaseVal'].forEach(function (id) {
      var e = $(id);
      if (e.offsetWidth && e.scrollWidth > e.clientWidth + 1) out.textOverflow.push(tag + ' ' + id);
    });
    out.bannerH.push($('banner').offsetHeight);
    if (out.portrait) out.stickGap.push(parseFloat($('phasebar').style.top) - $('banner').offsetHeight);
  }
  function canvases(view) {
    ['cvD', 'cvPA', 'cvPB', 'cvR1', 'cvR2'].forEach(function (id) {
      var c = $(id);
      if (c.offsetWidth) out.canvases[view + id] = [c.offsetWidth, c.offsetHeight, c.width];
    });
  }
  frame(last + 100);
  [0, 0.9, 1.5].forEach(function (k) { [0, 90, 150, 180, 270, 360].forEach(function (p) {
    S.k = k; S.ph[1] = p; update(); check('v1 k=' + k + ' ph=' + p);
  }); });
  S.k = 0.9; S.link = true; update(); frame(last + 100); canvases('v1 linked ');
  setMode(2);
  for (var p = 95; p <= 270; p += 5) { setPhase(p); check('v2 ph=' + p); }
  setPhase(120); frame(last + 100); canvases('v2 ');
  out.docWidth = [de.scrollWidth, vw];
  // scrolled down: banner and phase bar stay at the top, the plots pass under them
  scrollTo(0, 1200);
  out.scrollY = scrollY;
  out.bannerTop = $('banner').getBoundingClientRect().top;
  out.phaseTop = $('phasebar').getBoundingClientRect().top - $('banner').getBoundingClientRect().bottom;
  out.plotUnder = $('cvPA').getBoundingClientRect().bottom < $('phasebar').getBoundingClientRect().bottom;
  // the "?" notes cover the screen wherever the page is scrolled to, and fit across it
  showNotes(true);
  var n = $('notes').getBoundingClientRect(), nb = $('notesBody').getBoundingClientRect();
  out.notes = [n.top, n.height, nb.left, nb.right];
  out.err = $('err').textContent;
  parent.postMessage(JSON.stringify(out), '*');
})();
</script>
"""


@unittest.skipUnless(find_browser(), "needs Chrome, Edge or Chromium installed")
class Layout(unittest.TestCase):
    """Phone-sized checks.  Headless Chrome won't make a window narrower than
    about 512 px, so the page runs in an iframe of the phone's size: the
    iframe is the page's viewport, exactly as a phone screen would be."""

    def measure(self, w, h, dpr=1):
        page = HTML.read_text(encoding="utf-8").replace("</body>", PROBE + "</body>")
        frame = ('<!doctype html><html><body style="margin:0"><pre id="out"></pre>'
                 '<iframe src="page.html" width="%d" height="%d" style="border:0;display:block"></iframe>'
                 '<script>addEventListener("message", function (e) {'
                 ' document.getElementById("out").textContent = e.data; });</script>'
                 '</body></html>' % (w, h))
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "page.html").write_text(page, encoding="utf-8")
            (d / "frame.html").write_text(frame, encoding="utf-8")
            r = subprocess.run(
                [find_browser(), "--headless=new", "--disable-gpu", "--no-first-run",
                 "--hide-scrollbars",            # phones overlay their scrollbars
                 "--user-data-dir=" + str(d / "profile"), "--window-size=%d,%d" % (max(w, 600), h + 50),
                 "--force-device-scale-factor=%s" % dpr,
                 "--virtual-time-budget=3000", "--dump-dom", (d / "frame.html").as_uri()],
                capture_output=True, encoding="utf-8", errors="replace", timeout=120)
        m = re.search(r'<pre id="out">(.*?)</pre>', r.stdout, re.S)
        self.assertTrue(m and m.group(1), "probe never reported:\n" + r.stderr[-2000:])
        out = json.loads(m.group(1).replace("&quot;", '"').replace("&amp;", "&")
                         .replace("&lt;", "<").replace("&gt;", ">"))
        self.assertEqual(out["vw"], w, "the iframe trick didn't give a %d px viewport" % w)
        self.assertEqual(out["err"], "")
        return out

    def check_portrait(self, w, h, dpr=1):
        out = self.measure(w, h, dpr)
        self.assertTrue(out["portrait"], "%dx%d should get the portrait layout" % (w, h))
        self.assertEqual(out["transform"], "", "portrait layout must not be scaled")
        self.assertEqual(out["wide"], [], "sticks out past the right edge of a %d px screen" % w)
        self.assertEqual(out["textOverflow"], [], "text doesn't fit its box")
        self.assertLessEqual(out["docWidth"][0], out["docWidth"][1], "page scrolls sideways")
        # banner: same height in every state (else the phase bar jumps while dragging),
        # with the phase bar stuck 8 px under it
        self.assertEqual(len(set(out["bannerH"])), 1, "banner height changes: %s" % sorted(set(out["bannerH"])))
        self.assertEqual(set(out["stickGap"]), {8})
        self.assertGreater(out["scrollY"], 0, "page doesn't scroll")
        self.assertEqual(out["bannerTop"], 0, "banner didn't stick to the top")
        self.assertEqual(out["phaseTop"], 8, "phase bar didn't stick under the banner")
        self.assertTrue(out["plotUnder"], "plots should scroll under the sticky bars")
        top, height, left, right = out["notes"]
        self.assertEqual((top, height), (0, h), "notes should cover the screen")
        self.assertGreaterEqual(left, 0); self.assertLessEqual(right, w)
        # every plot gets the column's width and a readable height, and was drawn
        for name, (cw, ch, px) in out["canvases"].items():
            # (the block diagram is capped at 440 px: it only gets taller beyond that)
            self.assertGreaterEqual(cw, min(w, 440 if name.endswith("cvD") else 720) - 30, name)
            self.assertGreaterEqual(ch, 140, name)
            self.assertGreaterEqual(px, cw * max(2, dpr), name + " not drawn at full resolution")
        for name in ("v1 linked cvPA", "v1 linked cvR1", "v1 linked cvR2", "v2 cvR2"):
            self.assertIn(name, out["canvases"])
        return out

    def test_small_phone(self):            # iPhone SE (1st gen): the narrowest still around
        self.check_portrait(320, 568)

    def test_android_phone(self):
        self.check_portrait(360, 780)

    def test_iphone_at_3x(self):
        self.check_portrait(390, 844, dpr=3)

    def test_large_phone(self):
        self.check_portrait(430, 932)

    def test_tablet_portrait_is_capped_and_centred(self):
        self.check_portrait(820, 1180)

    def test_landscape_keeps_the_projector_layout(self):
        for w, h in ((844, 390), (1024, 768), (1180, 820)):
            out = self.measure(w, h)
            self.assertFalse(out["portrait"], "%dx%d" % (w, h))
            self.assertTrue(out["transform"].startswith("scale("), "%dx%d" % (w, h))


if __name__ == "__main__":
    unittest.main()
