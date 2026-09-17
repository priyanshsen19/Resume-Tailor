"""
LaTeX post-processing for LLM-generated resumes.

The pipeline is deliberately defensive: the model can return markdown fences,
commentary, a mangled preamble, unescaped special characters, or Unicode that
pdflatex cannot typeset.  Everything here is deterministic and idempotent, so
it is safe to run on already-clean LaTeX (e.g. the pristine template or a
hand-edited .tex file).

    raw model output
        -> extract_latex_document()   strip fences / chatter
        -> normalize_unicode()        smart quotes, dashes, arrows, emoji...
        -> split_body()               take ONLY the body; preamble comes from template
        -> sanitize_body()            LaTeX-aware escaping of & % # _ ^ $ ~
        -> assemble_document()        template preamble + body + \\end{document}
"""

import re
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Unicode normalisation
# ---------------------------------------------------------------------------

# Characters pdflatex (utf8 inputenc + T1) either cannot typeset or renders
# badly, mapped to safe ASCII / LaTeX equivalents.  Math replacements are
# wrapped in $...$ so sanitize_body() leaves them alone.
UNICODE_MAP = {
    # quotes / apostrophes
    "\u2018": "'", "\u2019": "'", "\u201a": ",", "\u201b": "'",
    "\u201c": "``", "\u201d": "''", "\u201e": ",,", "\u201f": "``",
    "\u2032": "'", "\u2033": "''", "\u00ab": "``", "\u00bb": "''",
    # dashes / hyphens
    "\u2010": "-", "\u2011": "-", "\u2012": "--", "\u2013": "--",
    "\u2014": "---", "\u2015": "---", "\u2212": "-",
    # spaces / invisibles
    "\u00a0": " ", "\u2002": " ", "\u2003": " ", "\u2009": " ", "\u202f": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\u2060": "", "\ufeff": "",
    # ellipsis / bullets
    "\u2026": "...", "\u2022": "$\\bullet$", "\u2023": "$\\bullet$",
    "\u25e6": "$\\circ$", "\u25aa": "$\\bullet$", "\u25cf": "$\\bullet$",
    "\u00b7": "$\\cdot$",
    # arrows
    "\u2192": "$\\rightarrow$", "\u2190": "$\\leftarrow$",
    "\u2194": "$\\leftrightarrow$", "\u21d2": "$\\Rightarrow$",
    "\u21d0": "$\\Leftarrow$", "\u2191": "$\\uparrow$", "\u2193": "$\\downarrow$",
    "\u27a1": "$\\rightarrow$", "\u279c": "$\\rightarrow$",
    # math-ish symbols
    "\u2265": "$\\geq$", "\u2264": "$\\leq$", "\u2260": "$\\neq$",
    "\u2248": "$\\approx$", "\u00d7": "$\\times$", "\u00f7": "$\\div$",
    "\u00b1": "$\\pm$", "\u221e": "$\\infty$", "\u00b0": "$^{\\circ}$",
    "\u2211": "$\\sum$", "\u221a": "$\\surd$", "\u00b2": "$^{2}$", "\u00b3": "$^{3}$",
    "\u00bd": "1/2", "\u00bc": "1/4", "\u00be": "3/4",
    # legal / currency
    "\u2122": "\\texttrademark{}", "\u00ae": "\\textregistered{}",
    "\u00a9": "\\textcopyright{}", "\u00a3": "\\pounds{}",
    "\u20b9": "Rs.", "\u20ac": "EUR", "\u00a5": "JPY",
    # check marks / misc decorations -> drop
    "\u2713": "", "\u2714": "", "\u2717": "", "\u2718": "", "\u2605": "", "\u2606": "",
}

# Anything beyond Latin Extended-B (accented letters are fine with utf8
# inputenc) is dropped: emoji, CJK, box-drawing, etc.
_MAX_SAFE_CODEPOINT = 0x024F


def normalize_unicode(text: str) -> str:
    """Map typographic Unicode to LaTeX-safe ASCII; drop what pdflatex can't set."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for src, dst in UNICODE_MAP.items():
        if src in text:
            text = text.replace(src, dst)
    out = []
    for ch in text:
        cp = ord(ch)
        if ch in "\n\t":
            out.append(ch)
        elif cp < 0x20 or cp == 0x7F:
            continue  # stray control chars
        elif cp > _MAX_SAFE_CODEPOINT:
            continue  # emoji / symbols with no font
        else:
            out.append(ch)
    return "".join(out)


# ---------------------------------------------------------------------------
# Extracting the LaTeX from model chatter
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```[ \t]*(?:latex|tex)?[ \t]*\r?\n(.*?)```", re.S | re.I)
_BEGIN_DOC_RE = re.compile(r"\\begin\s*\{\s*document\s*\}")
_END_DOC_RE = re.compile(r"\\end\s*\{\s*document\s*\}")


def extract_latex_document(raw: str) -> str:
    """Pull the LaTeX out of a model reply that may contain fences or prose."""
    text = (raw or "").strip()

    # Prefer a fenced block that actually contains the document.
    blocks = _FENCE_RE.findall(text)
    for block in blocks:
        if "\\documentclass" in block or _BEGIN_DOC_RE.search(block) or "\\section" in block:
            text = block
            break
    else:
        # Stray / unmatched fences: remove the fence markers only.
        text = re.sub(r"```[ \t]*(?:latex|tex)?[ \t]*", "", text, flags=re.I)

    # Drop anything before \documentclass (explanations, "Here is your resume:")
    m = text.find("\\documentclass")
    if m > 0:
        text = text[m:]

    # Drop anything after \end{document}
    m_end = _END_DOC_RE.search(text)
    if m_end:
        text = text[: m_end.end()]

    return text.strip()


# ---------------------------------------------------------------------------
# Splitting preamble / body
# ---------------------------------------------------------------------------

def split_document(tex: str) -> Tuple[Optional[str], Optional[str]]:
    """Return (preamble, body).  Either may be None if the marker is missing."""
    m_begin = _BEGIN_DOC_RE.search(tex)
    if not m_begin:
        return None, None
    preamble = tex[: m_begin.start()]
    rest = tex[m_begin.end():]
    m_end = _END_DOC_RE.search(rest)
    body = rest[: m_end.start()] if m_end else rest
    return preamble, body


def _body_anchors(template_body: str, count: int = 3):
    """First few meaningful lines of the template body, used to locate the
    body when the model forgot \\begin{document}."""
    anchors = []
    for line in template_body.split("\n"):
        s = line.strip()
        if s and not s.startswith("%") and s not in ("{", "}"):
            anchors.append(s)
        if len(anchors) >= count:
            break
    return anchors


def extract_body(tex: str, template_body: str) -> str:
    """Return the document body from model output, recovering if markers are missing."""
    _, body = split_document(tex)
    if body is not None:
        return body

    # No \begin{document}: locate body via known template anchors.
    for anchor in _body_anchors(template_body):
        idx = tex.find(anchor)
        if idx != -1:
            rest = tex[idx:]
            m_end = _END_DOC_RE.search(rest)
            return rest[: m_end.start()] if m_end else rest

    # No preamble at all but clearly resume content: treat whole thing as body.
    if "\\documentclass" not in tex and "\\section" in tex:
        m_end = _END_DOC_RE.search(tex)
        return tex[: m_end.start()] if m_end else tex

    raise ValueError("Could not locate the document body in the model output")


# ---------------------------------------------------------------------------
# LaTeX-aware sanitiser for the body
# ---------------------------------------------------------------------------

# Environments in which a bare & is an alignment tab, not text.
TABULAR_ENVS = {
    "tabular", "tabular*", "tabularx", "tabulary", "array", "longtable",
    "align", "align*", "aligned", "alignat", "eqnarray",
    "matrix", "pmatrix", "bmatrix", "vmatrix", "cases", "split",
}

# Commands whose first mandatory argument is verbatim-ish (URLs, paths, keys)
# and must never be escaped.
URL_ARG_COMMANDS = {
    "href", "url", "nolinkurl", "path", "includegraphics", "input", "include",
    "label", "ref", "pageref", "eqref", "cite", "hypersetup", "hyperref",
    "hypertarget", "hyperlink",
}


def _copy_brace_group(src: str, start: int) -> int:
    """`start` points at '{'. Return index just past the matching '}'."""
    depth = 0
    k = start
    n = len(src)
    while k < n:
        ch = src[k]
        if ch == "\\":
            k += 2
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return k + 1
        k += 1
    return n


def sanitize_body(body: str) -> str:
    """Escape special characters that appear as *text* in the document body.

    Rules:
      * Existing escapes (\\&, \\%, \\_, ...) are preserved verbatim - never doubled.
      * Comments (% not preceded by a digit) are copied untouched to end of line.
      * `42%` -> `42\\%`  (percent after a digit is a percentage, not a comment)
      * `&` is escaped unless inside a tabular-like environment.
      * `#`, `_`, `^` are always escaped in text mode.
      * `$5M` -> `\\$5M`; other `$` toggle math mode, whose contents are untouched.
      * `~25` -> `\\textasciitilde{}25` (approx sign, not a non-breaking space).
      * Arguments of \\href, \\url, etc. are copied verbatim.
    """
    out = []
    i, n = 0, len(body)
    in_math = False
    env_stack = []

    def in_tabular() -> bool:
        return any(e in TABULAR_ENVS for e in env_stack)

    def prev_char() -> str:
        for chunk in reversed(out):
            if chunk:
                return chunk[-1]
        return ""

    while i < n:
        c = body[i]

        # ---- control sequences & escaped characters -------------------------
        if c == "\\":
            if i + 1 >= n:
                out.append(c)
                i += 1
                continue
            nxt = body[i + 1]
            if nxt.isalpha():
                j = i + 1
                while j < n and body[j].isalpha():
                    j += 1
                name = body[i + 1:j]
                out.append(body[i:j])

                if name in ("begin", "end"):
                    m = re.match(r"\s*\{([^{}]*)\}", body[j:])
                    if m:
                        env = m.group(1).strip()
                        out.append(m.group(0))
                        j += m.end()
                        if name == "begin":
                            env_stack.append(env)
                        elif env in env_stack:
                            while env_stack and env_stack.pop() != env:
                                pass
                elif name in URL_ARG_COMMANDS:
                    m = re.match(r"\s*(?:\[[^\]]*\])?\s*(?=\{)", body[j:])
                    if m:
                        k = _copy_brace_group(body, j + m.end())
                        out.append(body[j:k])
                        j = k
                i = j
                continue

            # Control symbol: \\ \& \% \_ \# \$ \{ \} \( \) \[ \] \, \; ...
            if nxt in "([":
                in_math = True
            elif nxt in ")]":
                in_math = False
            out.append(body[i:i + 2])
            i += 2
            continue

        # ---- math mode ------------------------------------------------------
        if c == "$":
            if not in_math and i + 1 < n and body[i + 1].isdigit():
                out.append("\\$")          # currency: $5M
                i += 1
                continue
            in_math = not in_math
            out.append(c)
            i += 1
            continue

        if in_math:
            # A paragraph break inside math is always an error; assume the
            # model left a stray $ and resynchronise.
            if c == "\n" and body.startswith("\n", i + 1):
                in_math = False
            out.append(c)
            i += 1
            continue

        # ---- text-mode specials ---------------------------------------------
        if c == "%":
            if prev_char().isdigit():
                out.append("\\%")
                i += 1
                continue
            j = body.find("\n", i)       # real comment: copy to end of line
            j = n if j == -1 else j
            out.append(body[i:j])
            i = j
            continue

        if c == "&":
            out.append("&" if in_tabular() else "\\&")
            i += 1
            continue

        if c == "#":
            out.append("\\#")
            i += 1
            continue

        if c == "_":
            out.append("\\_")
            i += 1
            continue

        if c == "^":
            out.append("\\^{}")
            i += 1
            continue

        if c == "~" and i + 1 < n and body[i + 1].isdigit():
            out.append("\\textasciitilde{}")
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)


def repair_double_escapes(body: str) -> str:
    """Undo `\\\\&` / `\\\\#` / `95\\\\%` produced by earlier naive escaping.

    A real line break directly followed by & or # never occurs in resume
    LaTeX, and `<digit>\\\\%` is always a mangled percentage.
    """
    body = re.sub(r"\\\\([&#])", r"\\\1", body)
    body = re.sub(r"(?<=\d)\\\\%", r"\\%", body)
    # Escaped comments: `\%----HEADING----`, line-leading `\% Foo`, `} \% Award`
    body = re.sub(r"^([ \t]*)\\%", r"\1%", body, flags=re.M)
    body = re.sub(r"(?<=\s)\\%(?=-{2,})", "%", body)
    body = re.sub(r"(\}[ \t]+)\\%(?=[ \t]*[A-Za-z])", r"\1%", body)
    return body


# ---------------------------------------------------------------------------
# Whole-document assembly
# ---------------------------------------------------------------------------

def collapse_blank_lines(text: str) -> str:
    """Allow at most one blank line in a row (blank lines inside lists break LaTeX)."""
    return re.sub(r"\n[ \t]*\n(?:[ \t]*\n)+", "\n\n", text)


def assemble_document(preamble: str, body: str) -> str:
    preamble = preamble.rstrip("\n")
    body = collapse_blank_lines(body).strip("\n")
    return f"{preamble}\n\\begin{{document}}\n{body}\n\\end{{document}}\n"


def prepare_tex(raw_output: str, template_tex: str, use_template_preamble: bool = True) -> str:
    """Turn arbitrary model output (or a hand-edited .tex) into compilable LaTeX.

    When `use_template_preamble` is True the preamble is always taken from the
    template, so the model can only ever affect the body.
    """
    template_preamble, template_body = split_document(template_tex)
    if template_preamble is None:
        raise ValueError("Template is missing \\begin{document}")

    tex = extract_latex_document(raw_output)
    tex = normalize_unicode(tex)

    body = extract_body(tex, template_body)
    body = repair_double_escapes(body)
    body = sanitize_body(body)

    if use_template_preamble:
        preamble = template_preamble
    else:
        preamble, _ = split_document(tex)
        if preamble is None or "\\documentclass" not in preamble:
            preamble = template_preamble

    return assemble_document(preamble, body)


def latex_error_from_log(log_content: str) -> str:
    """Return the first LaTeX error with its context (through the `l.NN` line)."""
    lines = log_content.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("!"):
            chunk = [line]
            for extra in lines[i + 1:i + 12]:
                chunk.append(extra)
                if extra.startswith("l."):
                    # include the continuation line pdflatex prints after l.NN
                    nxt_idx = lines.index(extra, i + 1) + 1
                    if nxt_idx < len(lines):
                        chunk.append(lines[nxt_idx])
                    break
            return "\n".join(x for x in chunk if x.strip())
    return "pdflatex compilation failed (no error line found in log)"
