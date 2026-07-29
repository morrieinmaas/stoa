# SPDX-License-Identifier: Apache-2.0
"""Fifth corpus: UK primary and secondary legislation in CLML.

The genre this project is actually aimed at, and the one it had not tested.
Everything measured so far has been documents *about* public administration --
notices, standards, articles, forms. This is the statute itself: the archetypal
public document, the one with the strongest archival and citation requirements,
and the one where a wrong number matters most.

Source: legislation.gov.uk, which serves Crown Legislation Markup Language
directly. Chosen as a genre, not to satisfy any particular element -- picking
a corpus because it contains the element you want to justify is exactly the
gaming the evidence gate in docs/GOVERNANCE.md section 4 exists to prevent.

    python3 tools/legislation.py
    python3 tools/legislation.py --refresh
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
try:
    import xml.etree.ElementTree as ET
    ET.fromstring("<x/>")
except Exception:  # pragma: no cover
    sys.stderr.write("this Python has no pyexpat; use: mise run corpus-law\n")
    raise SystemExit(2)
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402
import htmlemit        # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "corpus" / "cache" / "law"
BASE = "https://www.legislation.gov.uk"

# A spread across type, era and size: constitutional, equality, information
# rights, data protection, and two pieces of secondary legislation.
ACTS = ["ukpga/1998/42", "ukpga/2000/36", "ukpga/2010/15", "ukpga/2018/12",
        "ukpga/2005/16", "ukpga/1990/18", "uksi/2019/419", "ukpga/2006/46"]

SECTIONISH = {"Part", "Chapter", "Pblock", "P1group", "P1", "P2", "P3", "P4",
              "P5", "P6", "Schedule", "Schedules", "Group", "PsubBlock"}
PARA_WRAP = {"P1para", "P2para", "P3para", "P4para", "P5para", "P6para",
             "Para", "BlockText", "BlockAmendment"}
MATHML = {"math", "mi", "mo", "mn", "mrow", "msub", "msup", "mfrac", "mtext",
          "mstyle", "msqrt", "mspace", "mtable", "mtr", "mtd", "mfenced"}
INLINE_TAGS = {"Emphasis", "Strong", "SmallCaps", "Citation", "CitationSubRef",
               "CommentaryRef", "Term", "Acronym", "Abbreviation",
               "Superior", "Inferior", "InlineAmendment", "Addition",
               "Substitution", "Repeal", "Character", "ExternalLink",
               "InternalLink", "Uri", "FootnoteRef", "Definition", "Span",
               "Title", "Subtitle", "Subject", "Proviso"}
SKIP = {"Metadata", "ukm:Metadata", "Resources", "atom:link", "Commentaries",
        "Footnotes", "Reference", "Number"}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "stoa-corpus/0 (research)"})
    with urllib.request.urlopen(req, timeout=120) as f:
        return f.read()


def fetch(refs, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for r in refs:
        p = CACHE / (r.replace("/", "_") + ".xml")
        if not p.exists() or refresh:
            try:
                p.write_bytes(_get(f"{BASE}/{r}/data.xml"))
                time.sleep(0.5)
            except (urllib.error.URLError, urllib.error.HTTPError) as e:
                print(f"  {r}: {e}", file=sys.stderr)
                continue
        out.append((r, p.read_bytes()))
    return out


def _t(s):
    return {"t": "text", "v": s}


def _p(*c):
    return {"t": "paragraph", "c": list(c)}


def _pair(k, blocks):
    return [{"t": "term", "c": [_t(k)]}, {"t": "definition", "c": blocks}]


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def tag(el):
    return el.tag.split("}")[-1]


def anchor(a):
    return re.sub(r"[^A-Za-z0-9_.:-]", "-", a or "") or "x"


class Findings:
    def __init__(self):
        self.escapes = Counter()
        self.notes = Counter()
        self.src = Counter()
        self.commentaries = 0


def keep(nodes):
    out = []
    for x in nodes:
        if x.get("t") == "text":
            if x.get("v"):
                out.append(x)
        elif x.get("t") in ("line-break", "power", "note-ref"):
            out.append(x)
        elif "c" in x:
            x["c"] = keep(x["c"])
            if x["c"]:
                out.append(x)
        else:
            out.append(x)
    return out


def inline_one(ch, f, ctx, prev=None):
    name = tag(ch)
    kids = inline(ch, f, ctx)
    txt = clean("".join(ch.itertext()))

    if name in MATHML:
        f.notes["MathML carried as verbatim text, not as structure"] += 1
        return [{"t": "code", "c": [_t(txt)]}] if txt else []
    if name in ("Emphasis", "Term", "Definition", "SmallCaps"):
        return [{"t": "emphasis", "c": kids}] if kids else []
    if name in ("Strong",):
        return [{"t": "strong", "c": kids}] if kids else []
    if name in ("Citation", "CitationSubRef", "ExternalLink", "InternalLink", "Uri"):
        # a citation to another instrument names a resource the reader may
        # choose to visit, which is a link, not a fetched subresource
        href = ch.get("URI") or ch.get("href") or ""
        if href and stoa.safe_iri(href):
            return [{"t": "link", "href": href, "c": kids or [_t(txt or href)]}]
        return kids or ([_t(txt)] if txt else [])
    if name in ("CommentaryRef", "FootnoteRef"):
        rid = ch.get("Ref") or ch.get("id") or ""
        ctx.setdefault("refs", set()).add(anchor(rid))
        return [{"t": "note-ref", "target": anchor(rid)}] if rid else []
    if name in ("Superior",):
        # a superior character in statute is a footnote marker or an ordinal,
        # not an exponent
        return kids or ([_t(txt)] if txt else [])
    if name in INLINE_TAGS:
        return kids or ([_t(txt)] if txt else [])
    f.escapes[f"inline <{name}>: no mapping"] += 1
    return kids or ([_t(txt)] if txt else [])


def inline(el, f, ctx):
    out = []
    if el.text and el.text.strip():
        out.append(_t(clean(el.text)))
    for ch in el:
        f.src[tag(ch)] += 1
        out.extend(inline_one(ch, f, ctx, out))
        if ch.tail and ch.tail.strip():
            out.append(_t(clean(ch.tail)))
    return keep(out)


def heading_of(el, f, ctx, depth):
    num = title = None
    for g in el:
        if tag(g) == "Pnumber":
            num = clean("".join(g.itertext()))
        elif tag(g) == "Number":
            num = num or clean("".join(g.itertext()))
        elif tag(g) == "Title":
            title = inline(g, f, ctx)
    parts = []
    if num:
        parts.append(_t(num + (". " if title else "")))
    if title:
        parts.extend(title)
    if not parts:
        return None
    return {"t": "heading", "level": min(max(depth, 1), 6), "c": keep(parts)}


def blocks(el, f, ctx, depth=0, titled=False):
    """`titled` means the caller already turned this element's <Title> into a
    heading. When it did not, a Title here is content and must not be dropped."""
    out = []
    loose = []

    def flush():
        if loose:
            c = keep(list(loose))
            if c:
                out.append({"t": "paragraph", "c": c})
            loose.clear()

    if el.text and el.text.strip():
        loose.append(_t(clean(el.text)))

    for ch in el:
        name = tag(ch)
        f.src[name] += 1

        if name in INLINE_TAGS:
            loose.extend(inline_one(ch, f, ctx, loose))
            if ch.tail and ch.tail.strip():
                loose.append(_t(clean(ch.tail)))
            continue

        flush()
        tail = _t(clean(ch.tail)) if (ch.tail and ch.tail.strip()) else None

        if name == "Title" and not titled:
            c = inline(ch, f, ctx)
            if c:
                out.append({"t": "heading",
                            "level": min(max(depth + 1, 1), 6), "c": c})
        elif name in SKIP or name in ("Pnumber", "Title", "Number"):
            pass
        elif name == "Text":
            c = inline(ch, f, ctx)
            if c:
                out.append({"t": "paragraph", "c": c})
        elif name in PARA_WRAP:
            out.extend(blocks(ch, f, ctx, depth))
        elif name == "TitleBlock":
            h = heading_of(ch, f, ctx, depth + 1)
            if h:
                out.append(h)
            else:
                sub = [x for x in inline(ch, f, ctx)]
                if sub:
                    out.append({"t": "heading",
                                "level": min(max(depth + 1, 1), 6), "c": sub})
        elif name in ("Subject", "SubjectInformation"):
            c = inline(ch, f, ctx)
            if c:
                out.append({"t": "paragraph", "c": c})
        elif name == "Contents":
            node = contents(ch, f, ctx, depth)
            if node:
                out.append(node)
        elif name in ("Schedule",):
            # a Schedule is a self-contained part of the instrument, which is
            # exactly what `article` means
            head = heading_of(ch, f, ctx, depth + 1)
            body = blocks(ch, f, ctx, depth + 1, titled=head is not None)
            if head or body:
                node = {"t": "article", "c": ([head] if head else []) + body}
                if ch.get("id"):
                    node["id"] = anchor(ch.get("id"))
                out.append(node)
        elif name in SECTIONISH:
            head = heading_of(ch, f, ctx, depth + 1)
            body = blocks(ch, f, ctx, depth + 1, titled=head is not None)
            if head or body:
                node = {"t": "section", "c": ([head] if head else []) + body}
                if ch.get("id"):
                    node["id"] = anchor(ch.get("id"))
                out.append(node)
        elif name in ("UnorderedList", "OrderedList"):
            items = []
            for li in ch:
                if tag(li) != "ListItem":
                    continue
                b = blocks(li, f, ctx, depth + 1)
                if b:
                    items.append({"t": "item", "c": b})
            if items:
                out.append({"t": "list", "ordered": name == "OrderedList",
                            "c": items})
        elif name in ("Tabular", "table"):
            node = table(ch, f, ctx, depth)
            if node:
                out.append(node)
        elif name == "Commentary":
            n = commentary(ch, f, ctx, depth)
            if n:
                out.append(n)
        elif name in ("Blockquote", "QuotedStructure"):
            b = blocks(ch, f, ctx, depth + 1)
            if b:
                out.append({"t": "quote", "c": b})
        else:
            sub = blocks(ch, f, ctx, depth + 1)
            if sub:
                out.extend(sub)
            elif clean("".join(ch.itertext())):
                f.escapes[f"block <{name}>: no mapping"] += 1

        if tail:
            loose.append(tail)

    flush()
    return out


def contents(el, f, ctx, depth):
    items = []
    for it in el.iter():
        if tag(it) not in ("ContentsItem", "ContentsPart", "ContentsChapter",
                           "ContentsPblock", "ContentsGroup"):
            continue
        num = title = ""
        for g in it:
            if tag(g) == "ContentsNumber":
                num = clean("".join(g.itertext()))
            elif tag(g) == "ContentsTitle":
                title = clean("".join(g.itertext()))
        label = clean(f"{num} {title}")
        if not label:
            continue
        ref = it.get("IdURI") or it.get("DocumentURI") or ""
        c = [_t(label)]
        if ref and stoa.safe_iri(ref):
            c = [{"t": "link", "href": ref, "c": [_t(label)]}]
        items.append({"t": "item", "c": [{"t": "paragraph", "c": c}]})
    return {"t": "contents", "c": items} if items else None


def table(el, f, ctx, depth):
    rows = []
    cap = None
    for g in el:
        if tag(g) in ("Title", "TableTitle", "TableText"):
            txt = clean("".join(g.itertext()))
            if txt:
                cap = [_t(txt)]
                break
    for tr in el.iter():
        if tag(tr) != "tr":
            continue
        cells = []
        for td in tr:
            if tag(td) not in ("td", "th"):
                continue
            body = blocks(td, f, ctx, depth + 1)
            if not body:
                c = inline(td, f, ctx)
                body = [{"t": "paragraph", "c": c}] if c else []
            cell = {"t": "header-cell" if tag(td) == "th" else "cell", "c": body}
            if tag(td) == "th":
                cell["scope"] = "column"
            cells.append(cell)
        if cells:
            rows.append({"t": "row", "c": cells})
    if not rows:
        return None
    kids = []
    if cap:
        kids.append({"t": "caption", "c": cap})
    kids.append({"t": "table-section", "kind": "body", "c": rows})
    return {"t": "table", "c": kids}


def commentary(el, f, ctx, depth):
    f.commentaries += 1
    body = blocks(el, f, ctx, depth + 1)
    if not body:
        c = inline(el, f, ctx)
        body = [{"t": "paragraph", "c": c}] if c else []
    if not body:
        return None
    cid = anchor(el.get("id") or f"c{f.commentaries}")
    return {"t": "note", "id": cid, "c": body}


def dedupe_ids(tree, f):
    seen = set()
    for n, _ in stoa.walk(tree):
        i = n.get("id")
        if not isinstance(i, str):
            continue
        if i in seen:
            del n["id"]
            f.notes["duplicate source id dropped from the later node"] += 1
        else:
            seen.add(i)
    return tree


def resolve_refs(tree, f):
    ids = {n["id"] for n, _ in stoa.walk(tree) if isinstance(n.get("id"), str)}
    dropped = [0]

    def go(node):
        kids = node.get("c")
        if not kids:
            return
        out = []
        for ch in kids:
            t = stoa.typ(ch)
            if t in ("reference", "citation", "note-ref") \
                    and ch.get("target") not in ids:
                dropped[0] += 1
                out.extend(ch.get("c") or [])
                continue
            go(ch)
            out.append(ch)
        node["c"] = out

    go(tree)
    if dropped[0]:
        f.notes["cross-reference with no emitted target: degraded"] += dropped[0]
    return tree


def to_stoa(ref, xml, f):
    root = ET.fromstring(xml)
    ctx = {}

    title = ""
    for e in root.iter():
        if tag(e) in ("Title", "dc:title") and not title:
            t = clean("".join(e.itertext()))
            if t:
                title = t
                break

    body = [{"t": "heading", "level": 1, "c": [_t(title or ref)]}]
    prov = _pair("Citation", [_p(_t(ref))])
    prov += _pair("Source", [_p({"t": "link", "href": f"{BASE}/{ref}",
                                 "c": [_t("legislation.gov.uk")]})])
    for e in root.iter():
        if tag(e) == "ukm:Year" or tag(e) == "Year":
            y = e.get("Value")
            if y and y.isdigit():
                prov += _pair("Year", [_p({"t": "date", "value": y,
                                           "precision": "year"})])
                break
    body.append({"t": "provenance", "c": prov})

    # commentaries carry the footnote bodies and live outside the provisions
    notes = []
    for e in root.iter():
        if tag(e) == "Commentary":
            n = commentary(e, f, ctx, 2)
            if n:
                notes.append(n)

    for part in ("Contents", "Primary", "Secondary", "Body", "Schedules"):
        for e in root.iter():
            if tag(e) == part:
                body.extend(blocks(e, f, ctx, 1))
                break

    body.extend(notes)
    doc = {"t": "document", "id": f"urn:stoa:uk-law:{ref.replace('/', '-')}",
           "lang": "en", "title": (title or ref)[:300], "c": body}
    return resolve_refs(dedupe_ids(doc, f), f)


def source_text(el, out, depth=0):
    if tag(el) in SKIP:
        return
    for s in (el.text, el.tail):
        s = clean(s)
        if s and len(s) > 3:
            out.append(s)
    for ch in el:
        source_text(ch, out, depth + 1)


def run(refresh, out_path):
    reg = stoa.Register()
    f = Findings()
    docs = fetch(ACTS, refresh)
    print(f"  {len(docs)} instruments", file=sys.stderr)

    ok = conf = noloss = 0
    err_rules = Counter()
    types_used = Counter()
    per_doc = []
    jb = hb = tb = xb = 0

    for ref, xml in docs:
        before = sum(f.escapes.values())
        try:
            doc = to_stoa(ref, xml, f)
        except Exception as e:
            per_doc.append((ref, f"mapping raised {type(e).__name__}: {e}"))
            continue
        doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))

        errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
        for d in errs:
            err_rules[d.rule] += 1

        want = []
        source_text(ET.fromstring(xml), want)
        carried = set(stoa.content_units(doc))
        blob = re.sub(r"\s+", " ",
                      "\n".join(stoa.project_text(stoa.to_l0(doc, reg))))
        lost = [s for s in want
                if s not in carried and re.sub(r"\s+", " ", s) not in blob]

        escaped = sum(f.escapes.values()) > before
        if not errs:
            conf += 1
        if not lost:
            noloss += 1
        if not errs and not lost and not escaped:
            ok += 1
        else:
            per_doc.append((ref, f"{len(errs)} errors, {len(lost)} lost, "
                            f"{'omission' if escaped else 'no omission'}"))

        for node, _ in stoa.walk(doc):
            if stoa.typ(node) in reg:
                types_used[stoa.typ(node)] += 1

        l0 = stoa.to_l0(doc, reg)
        jb += len(stoa.canonical_json(doc))
        hb += len(htmlemit.render(l0).encode("utf-8"))
        tb += len("\n".join(stoa.project_text(l0)).encode("utf-8"))
        xb += len(xml)

    total = len(docs) or 1
    lines = []
    w = lines.append
    w("# Corpus coverage: UK legislation (fifth genre)\n")
    w(f"Generated by `tools/legislation.py` over {total} Acts and instruments "
      f"in Crown Legislation Markup Language, from legislation.gov.uk.\n")
    w("This is the genre the project is aimed at and had not tested. The other "
      "corpora are documents *about* public administration; this is the statute "
      "itself -- the archetypal public document, with the strongest archival "
      "and citation requirements, and the one where a wrong number matters "
      "most.\n")

    w("## 1. Coverage\n")
    w(f"**{100.0 * ok / total:.0f}%** ({ok}/{total}) map with no element "
      f"outside the register, no conformance error, and no source string "
      f"dropped.\n")
    w("| Component | Result |")
    w("|---|---|")
    w(f"| Produce a conforming document | **{100.0 * conf / total:.0f}%** ({conf}/{total}) |")
    w(f"| Lose no source string | **{100.0 * noloss / total:.0f}%** ({noloss}/{total}) |")
    w(f"| Need no element outside the register | **{100.0 * ok / total:.0f}%** ({ok}/{total}) |")
    w("")
    if err_rules:
        for r, c in err_rules.most_common():
            w(f"- `{r}` x{c}")
        w("")
    if per_doc:
        for r, why in per_doc[:12]:
            w(f"- {r}: {why}")
        w("")

    w("## 2. Omissions\n")
    if f.escapes:
        for k, c in f.escapes.most_common(20):
            w(f"- {k} — x{c}")
    else:
        w("None.\n")
    if f.notes:
        w("\nMapping decisions recorded:\n")
        for k, c in f.notes.most_common(8):
            w(f"- {k} — x{c}")
    w("")

    w("## 3. Element mix\n")
    w(f"{len(types_used)} of {len(reg.elements)} register elements exercised.\n")
    w("| Element | Layer | Occurrences |")
    w("|---|---|---|")
    for name, c in types_used.most_common():
        w(f"| `{name}` | L{reg.layer(name)} | {c:,} |")
    w("")

    w("## 4. Envelope\n")
    w("| | source CLML | Stoa canonical | Stoa HTML | L0 text |")
    w("|---|---|---|---|---|")
    w(f"| mean bytes / instrument | {xb // total:,} | {jb // total:,} | "
      f"{hb // total:,} | {tb // total:,} |")
    w("")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[written to {out_path}]", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "corpus" / "RESULTS-law.md"))
    a = ap.parse_args()
    return run(a.refresh, a.out)


if __name__ == "__main__":
    sys.exit(main())
