"""
Build-time / CI self-test: run the default template through the same
pipeline the API uses and compile it with pdflatex.  Exits non-zero if any
TeX package the template needs is missing, so a broken image never ships.

    python selftest_latex.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from latex_utils import prepare_tex, latex_error_from_log

template = (Path(__file__).parent / "templates" / "default_resume.tex").read_text()
tex = prepare_tex(template, template, use_template_preamble=True)

with tempfile.TemporaryDirectory() as tmp:
    tex_path = Path(tmp) / "selftest.tex"
    tex_path.write_text(tex)
    result = subprocess.run(
        ["pdflatex", "-interaction=nonstopmode", "-halt-on-error",
         f"-output-directory={tmp}", str(tex_path)],
        capture_output=True, text=True, env=os.environ.copy(),
    )
    pdf = tex_path.with_suffix(".pdf")
    if result.returncode != 0 or not pdf.exists():
        log = tex_path.with_suffix(".log")
        print("LaTeX self-test FAILED:", file=sys.stderr)
        print(latex_error_from_log(log.read_text(errors="ignore")) if log.exists() else result.stdout[-2000:],
              file=sys.stderr)
        sys.exit(1)
    print(f"LaTeX self-test OK ({pdf.stat().st_size} bytes)")
