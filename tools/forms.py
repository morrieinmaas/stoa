# SPDX-License-Identifier: Apache-2.0
"""Fourth corpus: real public-sector forms, to test L2.

`spec/EVIDENCE.md` reports 12 elements resting on the author's judgement rather
than on evidence, on the grounds that no corpus of *published static documents*
can contain a form. That is true and it is also a convenient excuse, because
public bodies publish forms constantly -- search forms, filters, consultation
responses, service start pages. They are documents with reader-initiated
interaction, which is precisely what L2 claims to cover.

So this stops treating L2 as unfalsifiable and measures it. Three questions:

  1. Coverage      can real public forms be expressed in L2 at all?
  2. Labels        `field.label` is required and non-empty, so an unlabelled
                   control is unrepresentable. How many real ones have none?
  3. Boundary      `form.action` is typed `path`, so a form cannot post across
                   origins. How many real ones do?

Questions 2 and 3 are the accessibility and fetch-boundary claims applied to
interaction, and they are the same shape as the alt-text measurement in the
scholarly corpus: not "does the format encourage good practice" but "is bad
practice expressible at all".

    python3 tools/forms.py
    python3 tools/forms.py --refresh
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402
import htmlemit        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "corpus" / "cache" / "forms"

# Public-sector and public-institution pages that serve real server-rendered
# forms. Chosen because they are public documents with interaction, not because
# their markup is good -- the point is to measure what real markup does.
PAGES = [
    "https://www.gov.uk/search/all",
    "https://www.gov.uk/browse/benefits",
    "https://www.gov.uk/browse/tax",
    "https://www.gov.uk/search/news-and-communications",
    "https://www.gov.uk/search/guidance-and-regulation",
    "https://www.ecb.europa.eu/home/search/html/index.en.html",
    "https://diavgeia.gov.gr/",
    "https://www.europarl.europa.eu/portal/en",
    "https://www.bundesregierung.de/breg-de/suche",
    "https://www.rijksoverheid.nl/documenten",
]

CONTROL = {"input", "select", "textarea", "button"}
TEXTISH = {"text", "email", "tel", "url", "search", "password", "number",
           "date", "time", "month", "week", "datetime-local", "color", "range"}
CHOICEISH = {"radio", "checkbox"}
SUBMITISH = {"submit", "button", "image", "reset"}
IGNORE_TYPE = {"hidden"}


class FormParser(HTMLParser):
    """Collects forms, their controls, and label associations. Deliberately
    tolerant: real public markup is not well-formed and the question is what it
    contains, not whether it validates."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.details = 0
        self.stack = []
        self.cur = None
        self.label_for = {}        # id -> label text
        self.open_label = None
        self.label_text = []
        self.wrapped = []          # controls inside the currently open label
        self.pending_text = []
        self.cur_select = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self.cur = {"action": a.get("action", ""), "method": a.get("method", "get"),
                        "controls": []}
        elif tag == "details":
            self.details += 1
        elif tag == "label":
            self.open_label = a.get("for")
            self.label_text = []
            self.wrapped = []
        elif tag == "select" and self.cur is not None:
            self.cur_select = {"kind": "select", "name": a.get("name", ""),
                               "id": a.get("id"), "options": [],
                               "multiple": "multiple" in a,
                               "aria": a.get("aria-label") or a.get("title")}
            self.cur["controls"].append(self.cur_select)
            if self.open_label is not None:
                self.wrapped.append(self.cur_select)
        elif tag == "option" and self.cur_select is not None:
            self.cur_select["options"].append({"value": a.get("value", ""),
                                               "label": a.get("label", ""),
                                               "text": ""})
            self.pending_text = ["option"]
        elif tag in ("input", "textarea", "button") and self.cur is not None:
            t = (a.get("type") or ("textarea" if tag == "textarea" else "text")).lower()
            if t in IGNORE_TYPE:
                return
            c = {"kind": tag, "type": t, "name": a.get("name", ""),
                 "id": a.get("id"), "value": a.get("value", ""),
                 "multiline": tag == "textarea",
                 "aria": a.get("aria-label") or a.get("title"),
                 "placeholder": a.get("placeholder"),
                 "required": "required" in a}
            self.cur["controls"].append(c)
            if self.open_label is not None:
                self.wrapped.append(c)

    def handle_endtag(self, tag):
        if tag == "form" and self.cur is not None:
            self.forms.append(self.cur)
            self.cur = None
        elif tag == "select":
            self.cur_select = None
        elif tag == "option":
            self.pending_text = []
        elif tag == "label":
            txt = re.sub(r"\s+", " ", "".join(self.label_text)).strip()
            if self.open_label:
                self.label_for[self.open_label] = txt
            for c in self.wrapped:
                c["wrapped_label"] = txt
            self.open_label = None
            self.label_text = []
            self.wrapped = []

    def handle_data(self, d):
        if self.pending_text and self.cur_select is not None \
                and self.cur_select["options"]:
            self.cur_select["options"][-1]["text"] += d
        if self.open_label is not None:
            self.label_text.append(d)


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; stoa-corpus/0; research)",
        "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as f:
        return f.read()


def fetch(urls, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for u in urls:
        key = re.sub(r"[^A-Za-z0-9]+", "_", u)[:80] + ".html"
        p = CACHE / key
        if not p.exists() or refresh:
            try:
                p.write_bytes(_get(u))
                time.sleep(0.4)
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                print(f"  {u}: {e}", file=sys.stderr)
                continue
        out.append((u, p.read_text(encoding="utf-8", errors="replace")))
    return out


# --------------------------------------------------------------------------

def _t(s):
    return {"t": "text", "v": s}


class Findings:
    def __init__(self):
        self.controls = 0
        self.unlabelled = 0
        self.label_from_aria = 0
        self.label_from_placeholder = 0
        self.no_label_anywhere = 0
        self.actions = 0
        self.cross_origin = 0
        self.escapes = Counter()
        self.notes = Counter()


def label_of(c, parser, f):
    """`field.label` is required and non-empty, so a control with no label of
    any kind is unrepresentable. Count how each one had to be rescued."""
    if c.get("id") and parser.label_for.get(c["id"], "").strip():
        return parser.label_for[c["id"]].strip()
    if c.get("wrapped_label", "").strip():
        return c["wrapped_label"].strip()
    f.unlabelled += 1
    if c.get("aria"):
        f.label_from_aria += 1
        return c["aria"].strip()
    if c.get("placeholder"):
        f.label_from_placeholder += 1
        return c["placeholder"].strip()
    f.no_label_anywhere += 1
    return ""


def to_form(fm, parser, f, idx):
    """One HTML form -> one L2 `form`, or nothing if it cannot be expressed."""
    action = (fm.get("action") or "").strip()
    f.actions += 1
    if stoa.PATH_REJECT.match(action):
        # form.action is typed `path`: a form that posts to another origin is
        # not expressible. Correct, and worth counting.
        f.cross_origin += 1
        f.escapes[f"form action names another origin: {action[:48]}"] += 1
        return None

    kids = []
    for c in fm["controls"]:
        t = c.get("type", "")
        if c["kind"] == "button" or t in SUBMITISH:
            label = (c.get("value") or c.get("aria")
                     or c.get("wrapped_label") or "Submit").strip()
            kids.append({"t": "submit", "label": label})
            continue
        f.controls += 1
        label = label_of(c, parser, f)
        if not label:
            # unrepresentable: skipped and counted rather than invented
            continue
        field = {"t": "field", "name": c.get("name") or f"field-{len(kids)}",
                 "label": label}
        if c.get("required"):
            field["required"] = True
        if c["kind"] == "select":
            opts = []
            for o in c["options"]:
                v = (o.get("value") or "").strip()
                txt = re.sub(r"\s+", " ", o.get("text") or o.get("label") or v).strip()
                if not txt:
                    continue
                opt = {"t": "field-option", "value": v or txt,
                       "c": [_t(txt)]}
                opts.append(opt)
            if not opts:
                continue
            field["c"] = [{"t": "field-choice", "multiple": bool(c.get("multiple")),
                           "c": opts}]
        elif t in CHOICEISH:
            field["c"] = [{"t": "field-choice", "multiple": t == "checkbox",
                           "c": [{"t": "field-option",
                                  "value": c.get("value") or "on",
                                  "c": [_t(label)]}]}]
        else:
            ft = {"t": "field-text"}
            if c.get("multiline"):
                ft["multiline"] = True
            if c.get("value"):
                ft["value"] = c["value"]
            field["c"] = [ft]
        kids.append(field)

    if not [k for k in kids if k["t"] == "field"]:
        return None
    if not any(k["t"] == "submit" for k in kids):
        kids.append({"t": "submit", "label": "Submit"})
    method = "post" if (fm.get("method") or "get").lower() == "post" else "get"
    return {"t": "form", "action": action or "search", "method": method,
            "c": kids}


def to_stoa(url, html, f):
    p = FormParser()
    try:
        p.feed(html)
    except Exception as e:
        f.notes[f"parser gave up: {type(e).__name__}"] += 1

    host = urllib.parse.urlparse(url).netloc
    body = [{"t": "heading", "level": 1, "c": [_t(f"Forms published at {host}")]},
            {"t": "provenance", "c": [
                {"t": "term", "c": [_t("Source")]},
                {"t": "definition", "c": [{"t": "paragraph", "c": [
                    {"t": "link", "href": url, "c": [_t(url)]}]}]}]}]

    n = 0
    for i, fm in enumerate(p.forms):
        node = to_form(fm, p, f, i)
        if node:
            body.append(node)
            n += 1
    for _ in range(p.details):
        # <details>/<summary> is exactly `disclosure`: collapsing is a reader
        # affordance and the content is present either way
        body.append({"t": "disclosure", "summary": "Details", "open": False,
                     "c": [{"t": "paragraph", "c": [_t("Collapsible content.")]}]})

    # a link that carries query state is `state-link`: state is addressable,
    # so it degrades to an ordinary link to the same document in that state
    q = re.findall(r'href="[^"]*\?([a-zA-Z0-9_]+)=([^"&]{1,40})"', html)[:5]
    if q:
        body.append({"t": "paragraph", "c":
                     [{"t": "state-link", "key": k, "value": v,
                       "c": [_t(f"{k}={v}")]} for k, v in q]})

    return {"t": "document",
            "id": f"urn:stoa:forms:{re.sub(r'[^a-z0-9]+', '-', host.lower())}",
            "lang": "en", "title": f"Forms published at {host}", "c": body}, n


def run(refresh, out_path):
    reg = stoa.Register()
    f = Findings()
    pages = fetch(PAGES, refresh)
    print(f"  {len(pages)} pages", file=sys.stderr)

    types_used = Counter()
    ok = forms_total = 0
    err_rules = Counter()
    per_page = []

    for url, html in pages:
        doc, n = to_stoa(url, html, f)
        forms_total += n
        doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))
        errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
        for d in errs:
            err_rules[d.rule] += 1
        if not errs:
            ok += 1
        else:
            per_page.append((url, f"{len(errs)} errors: {errs[0]}"))
        for node, _ in stoa.walk(doc):
            if stoa.typ(node) in reg:
                types_used[stoa.typ(node)] += 1
        # the projection must conform too
        l0 = stoa.to_l0(doc, reg)
        bad = [d for d in stoa.validate(l0, reg) if d.sev == "error"]
        if bad:
            per_page.append((url, f"projection invalid: {bad[0]}"))
        htmlemit.render(l0)

    total = len(pages) or 1
    lines = []
    w = lines.append
    w("# Corpus coverage: public-sector forms (L2)\n")
    w(f"Generated by `tools/forms.py` over {total} public-sector pages carrying "
      f"{forms_total} expressible forms.\n")
    w("The other three corpora are static documents, which cannot contain a "
      "form, so L2 was recorded as unfalsifiable. Public bodies publish forms "
      "constantly, so that was an excuse rather than a limit. This measures it.\n")

    w("## 1. Coverage\n")
    w(f"**{100.0 * ok / total:.0f}%** ({ok}/{total}) of pages produce a "
      f"conforming document whose L0 projection also conforms.\n")
    if err_rules:
        for r, c in err_rules.most_common():
            w(f"- `{r}` x{c}")
        w("")
    if per_page:
        for u, why in per_page[:10]:
            w(f"- {u}: {why}")
        w("")

    w("## 2. Labels: the accessibility claim applied to interaction\n")
    w("`field.label` is a required, non-empty field, so **an unlabelled control "
      "is unrepresentable**. There is no `<input>` with no label to write.\n")
    pct = (100.0 * f.unlabelled / f.controls) if f.controls else 0
    w(f"| | Count |")
    w(f"|---|---|")
    w(f"| Controls encountered | **{f.controls}** |")
    w(f"| With a real `<label>` (for= or wrapping) | "
      f"**{f.controls - f.unlabelled}** ({100 - pct:.0f}%) |")
    w(f"| With **no** `<label>` at all | **{f.unlabelled}** ({pct:.0f}%) |")
    w(f"| — rescued from `aria-label`/`title` | {f.label_from_aria} |")
    w(f"| — rescued from `placeholder` | {f.label_from_placeholder} |")
    w(f"| — **no label of any kind, unrepresentable** | "
      f"**{f.no_label_anywhere}** |")
    w("")
    w("A placeholder is not a label: it disappears on focus and is not "
      "announced reliably. Counting those separately is the point — in HTML "
      "they pass, here they had to be promoted to a real label or dropped.\n")

    w("## 3. The fetch boundary applied to submission\n")
    w("`form.action` is typed `path`, so **a form cannot post across "
      "origins**. Not discouraged: unrepresentable.\n")
    w(f"- Form actions examined: **{f.actions}**")
    w(f"- Naming another origin, therefore inexpressible: "
      f"**{f.cross_origin}** ({100.0 * f.cross_origin / max(1, f.actions):.0f}%)\n")

    w("## 4. L2 elements exercised\n")
    w("| Element | Layer | Occurrences |")
    w("|---|---|---|")
    for name in ("form", "field", "field-text", "field-choice", "field-option",
                 "submit", "disclosure", "tab-group", "tab", "state-link"):
        c = types_used.get(name, 0)
        w(f"| `{name}` | L{reg.layer(name)} | {c:,} |")
    w("")
    missing = [n for n in ("form", "field", "field-text", "field-choice",
                           "field-option", "submit", "disclosure", "tab-group",
                           "tab", "state-link") if not types_used.get(n)]
    if missing:
        w(f"Still unexercised by real documents: "
          f"{', '.join('`' + m + '`' for m in missing)}.\n")
        w("`tab-group` and `tab` are the honest problem: tabbed content on the "
          "public web is built with scripts, so a server-rendered corpus cannot "
          "reach them. They are two elements justified by nothing but the "
          "author's judgement, and the finite-vocabulary argument says that is "
          "a reason to remove them rather than to keep looking.\n")

    w("## 5. Omissions\n")
    if f.escapes:
        for k, c in f.escapes.most_common(12):
            w(f"- {k} — x{c}")
    else:
        w("None.\n")
    w("")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[written to {out_path}]", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "corpus" / "RESULTS-forms.md"))
    a = ap.parse_args()
    return run(a.refresh, a.out)


if __name__ == "__main__":
    sys.exit(main())
