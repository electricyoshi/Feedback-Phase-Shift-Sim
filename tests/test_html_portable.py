"""Will feedback_phase_sim.html open on a student's PC or Mac?

Static checks (always run): one self-contained file, nothing fetched, no
syntax that old Safari chokes on.  Browser checks (skipped when no Chrome,
Edge or Chromium is installed): load it from file:// in a real headless
browser and confirm the script ran in both views without an error.
"""
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
        self.has(dom, "Negative feedback — the difference shrinks")
        for c in ("cvD", "cvPA", "cvPB", "cvR1"):
            self.drawn(dom, c)

    def test_view_2_runs_from_file_url(self):
        dom = self.dump("#2")
        self.check_no_error(dom)
        self.has(dom, "Phase margin +60°")
        self.has(dom, "Gain margin +9.4 dB")
        for c in ("cvD", "cvPA", "cvPB", "cvR1", "cvR2"):
            self.drawn(dom, c)


if __name__ == "__main__":
    unittest.main()
