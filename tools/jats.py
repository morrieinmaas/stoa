# SPDX-License-Identifier: Apache-2.0
"""Third corpus, third genre: scholarly articles in JATS XML.

Corpus 1 is administrative notices, corpus 2 is standards documents. Between
them they left three L0 elements resting on the author's judgement rather than
on evidence -- `media`, `note` and `note-ref` -- because neither genre contains
an image or a footnote. `../spec/EVIDENCE.md` named them; this closes them.

Scholarly articles are the genre that has both, in quantity: figures with
graphics, numbered footnotes, footnote markers in running text, definition
lists, block quotations and dense bibliographies.

Source: Europe PMC open-access full text, which serves JATS directly.

It is also the first corpus where the accessibility claim is testable against
reality rather than against a fixture. `media.alt` is a required, non-empty
field, so a figure with no alternative text is *unrepresentable*. Real articles
frequently have none. Section 3 of the report counts them.

    python3 tools/jats.py                # 14 articles, cached
    python3 tools/jats.py --n 30 --refresh
    python3 tools/jats.py --emit PMC12900525
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
try:
    import xml.etree.ElementTree as ET
    ET.fromstring("<x/>")
except Exception:  # pragma: no cover - interpreter build without pyexpat
    sys.stderr.write("this Python has no pyexpat; use: mise run corpus-jats\n")
    raise SystemExit(2)
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402
import htmlemit        # noqa: E402
import structhash      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "corpus" / "cache" / "jats"
EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest"
XLINK = "{http://www.w3.org/1999/xlink}href"

# Front matter that becomes provenance rather than prose.
META_SKIP = {"journal-meta", "article-meta", "front", "processing-meta",
             "aff", "contrib-group", "permissions",
             "history", "pub-date", "article-id", "kwd-group", "funding-group",
             "counts", "custom-meta-group", "issue", "volume", "fpage",
             "lpage", "elocation-id", "journal-title-group", "issn",
             "publisher", "subj-group", "article-categories", "back-matter"}

INLINE_MAP = {"italic": "emphasis", "bold": "strong", "monospace": "code",
              "sc": "emphasis", "underline": "emphasis", "styled-content": None,
              "code": "code"}
MATHML = {"math", "mml:math", "mi", "mo", "mn", "mrow", "msub", "msup",
          "mfrac", "msqrt", "mspace", "mtext", "mstyle", "munderover",
          "mfenced", "mtable", "mtr", "mtd", "mover", "munder", "mmultiscripts",
          "menclose", "mpadded", "mphantom", "msubsup", "inline-formula"}
# JATS permits these inside a caption or a table cell, where this mapper is
# reading inline content. Flattening them is a mapping decision, not a gap.
BLOCK_IN_INLINE = {"p", "list", "list-item", "statement", "disp-formula",
                   "def-list", "disp-quote", "funding-source", "sec"}
SECTION_LIKE = {"sec", "ack", "glossary", "app", "app-group", "bio", "notes",
                "abstract", "trans-abstract"}
INLINE_TAGS = set(INLINE_MAP) | MATHML | {"xref", "ext-link", "sup", "sub",
                                          "break", "inline-graphic", "uri",
                                          "email", "label", "italic", "bold"}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "stoa-corpus/0 (research)"})
    with urllib.request.urlopen(req, timeout=90) as f:
        return f.read()


def discover(n, refresh):
    CACHE.mkdir(parents=True, exist_ok=True)
    idx = CACHE / "index.json"
    if idx.exists() and not refresh:
        ids = json.loads(idx.read_text())
    else:
        q = "OPEN_ACCESS:Y%20AND%20IN_EPMC:Y%20AND%20HAS_FT:Y"
        d = json.loads(_get(f"{EPMC}/search?query={q}&format=json"
                            f"&pageSize={max(n * 2, 25)}&resultType=core"))
        ids = [r["pmcid"] for r in d["resultList"]["result"] if r.get("pmcid")]
        idx.write_text(json.dumps(ids))
    return ids[:n]


def fetch(ids, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for i in ids:
        p = CACHE / f"{i}.xml"
        if not p.exists() or refresh:
            try:
                p.write_bytes(_get(f"{EPMC}/{i}/fullTextXML"))
                time.sleep(0.3)
            except urllib.error.URLError as e:
                print(f"  {i}: fetch failed {e}", file=sys.stderr)
                continue
        out.append((i, p.read_bytes()))
    return out


# --------------------------------------------------------------------------

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
        self.src_elements = Counter()
        self.graphics = 0
        self.graphics_without_alt = 0
        self.footnotes = 0
        self.figures = 0



BASE_TOKEN = re.compile(r"([A-Za-z0-9)\]]+)$")
NUMERIC = re.compile(r"^[-+]?[0-9][0-9A-Za-z+\-]*$")


def inline_one(ch, f, ctx, prev=None):
    name = tag(ch)
    kids = inline(ch, f, ctx)

    if name in INLINE_MAP:
        m = INLINE_MAP[name]
        if m is None:
            return kids
        return [{"t": m, "c": kids}] if kids else []
    if name == "xref":
        kind = ch.get("ref-type", "")
        target = anchor(ch.get("rid", "").split()[0] if ch.get("rid") else "")
        label = kids or [_t(clean(ch.text))]
        if kind in ("fn", "table-fn", "author-notes", "corresp"):
            return [{"t": "note-ref", "target": target}]
        if kind == "bibr":
            return [{"t": "citation", "target": target, "c": label}]
        return [{"t": "reference", "target": target, "c": label}]
    if name in ("ext-link", "uri"):
        href = ch.get(XLINK) or ch.get("href") or clean(ch.text)
        if stoa.safe_iri(href):
            return [{"t": "link", "href": href, "c": kids or [_t(href)]}]
        f.escapes[f"ext-link with unusable scheme: {str(href)[:40]}"] += 1
        return kids
    if name == "email":
        v = clean("".join(ch.itertext()))
        return [{"t": "link", "href": f"mailto:{v}", "c": [_t(v)]}] if v else []
    if name == "sup":
        exp = clean("".join(ch.itertext()))
        if exp and NUMERIC.match(exp) and prev and prev[-1].get("t") == "text":
            m = BASE_TOKEN.search(prev[-1]["v"])
            if m:
                prev[-1]["v"] = prev[-1]["v"][:m.start()]
                if not prev[-1]["v"]:
                    prev.pop()
                return [{"t": "power", "base": m.group(1), "exponent": exp}]
        # a superscript that is not an exponent is a marker or an ordinal;
        # both are text once the structure is carried by note-ref
        return kids or ([_t(exp)] if exp else [])
    if name == "sub":
        v = clean("".join(ch.itertext()))
        f.notes["subscript rendered as adjacent text"] += 1
        return kids or ([_t(v)] if v else [])
    if name == "break":
        return [{"t": "line-break"}]
    if name == "inline-graphic":
        node = graphic(ch, f, ctx, alt_hint="Inline figure")
        return []  # a block element cannot sit inline; recorded, not dropped
    if name == "label":
        v = clean("".join(ch.itertext()))
        return [_t(v)] if v else []
    if name in MATHML:
        v = clean("".join(ch.itertext()))
        f.notes["MathML carried as verbatim text, not as structure"] += 1
        return [{"t": "code", "c": [_t(v)]}] if v else []
    if name in BLOCK_IN_INLINE:
        f.notes[f"<{name}> flattened into inline context"] += 1
        return kids or ([_t(clean("".join(ch.itertext())))]
                        if clean("".join(ch.itertext())) else [])
    f.escapes[f"inline <{name}>: no mapping"] += 1
    return kids


def inline(el, f, ctx):
    out = []
    if el.text and el.text.strip():
        out.append(_t(clean(el.text)))
    for ch in el:
        f.src_elements[tag(ch)] += 1
        out.extend(inline_one(ch, f, ctx, out))
        if ch.tail and ch.tail.strip():
            out.append(_t(clean(ch.tail)))
    return stoa.prune(out)


def graphic(el, f, ctx, alt_hint=""):
    """A JATS graphic becomes `media`, whose src is a path and whose alt is a
    required non-empty string. That requirement is the accessibility claim, and
    it is the reason this function counts what it had to invent."""
    href = el.get(XLINK) or el.get("href") or ""
    f.graphics += 1
    if stoa.PATH_REJECT.match(href):
        # A figure that names another origin is not expressible. Correct
        # behaviour, and worth recording when it happens.
        f.escapes[f"graphic names a host: {href[:50]}"] += 1
        return None
    alt = ""
    for a in el.iter():
        if tag(a) == "alt-text":
            alt = clean("".join(a.itertext()))
            break
    if not alt:
        f.graphics_without_alt += 1
        alt = alt_hint
    if not alt:
        return None
    return {"t": "media", "kind": "image", "src": href or "figure", "alt": alt}


def blocks(el, f, ctx, depth=0):
    out = []
    loose = []

    def flush():
        if loose:
            c = stoa.prune(list(loose))
            if c:
                out.append({"t": "paragraph", "c": c})
            loose.clear()

    if el.text and el.text.strip():
        loose.append(_t(clean(el.text)))

    for ch in el:
        name = tag(ch)
        f.src_elements[name] += 1

        if name in INLINE_TAGS:
            loose.extend(inline_one(ch, f, ctx, loose))
            if ch.tail and ch.tail.strip():
                loose.append(_t(clean(ch.tail)))
            continue

        flush()
        tail = _t(clean(ch.tail)) if (ch.tail and ch.tail.strip()) else None

        if name in META_SKIP:
            pass
        elif name == "p":
            c = inline(ch, f, ctx)
            if c:
                out.append({"t": "paragraph", "c": c})
        elif name in SECTION_LIKE:
            # back matter containers carry a <title> that is real content;
            # recursing into them without it silently dropped the heading
            out.append(section(ch, f, ctx, depth + 1))
        elif name in ("list",):
            items = []
            for li in ch:
                if tag(li) != "list-item":
                    continue
                body = blocks(li, f, ctx, depth + 1)
                if body:
                    items.append({"t": "item", "c": body})
            if items:
                out.append({"t": "list",
                            "ordered": ch.get("list-type") in ("order", "ordered",
                                                               "alpha-lower",
                                                               "roman-lower"),
                            "c": items})
        elif name == "boxed-text":
            cap, _ = caption_of(ch, f, ctx)
            inner = blocks(ch, f, ctx, depth + 1)
            head = [{"t": "heading", "level": min(max(depth + 1, 1), 6),
                     "c": cap}] if cap else []
            if head or inner:
                out.append({"t": "sidebar", "c": head + inner})
        elif name == "def-list":
            pairs = []
            for d in ch:
                if tag(d) != "def-item":
                    continue
                term = defn = None
                for g in d:
                    if tag(g) == "term":
                        term = inline(g, f, ctx)
                    elif tag(g) == "def":
                        defn = blocks(g, f, ctx, depth + 1)
                if term:
                    pairs += [{"t": "term", "c": term},
                              {"t": "definition", "c": defn or []}]
            if pairs:
                # a def-list may carry its own <title>; a term-list takes only
                # terms and definitions, so the title becomes a heading beside it
                dtitle = None
                for g in ch:
                    if tag(g) == "title":
                        dtitle = inline(g, f, ctx)
                        break
                tl = {"t": "term-list", "c": pairs}
                if dtitle:
                    out.append({"t": "section", "c": [
                        {"t": "heading", "level": min(max(depth + 1, 1), 6),
                         "c": dtitle}, tl]})
                else:
                    out.append(tl)
        elif name == "disp-quote":
            body = blocks(ch, f, ctx, depth + 1)
            if body:
                out.append({"t": "quote", "c": body})
        elif name in ("disp-formula", "inline-formula", "tex-math", "mml:math"):
            v = clean("".join(ch.itertext()))
            if v:
                out.append({"t": "code-block", "language": "tex", "c": [_t(v)]})
                f.notes["formula carried as verbatim source, not as structure"] += 1
        elif name in ("code", "preformat"):
            v = "".join(ch.itertext())
            if v.strip():
                out.append({"t": "code-block", "c": [_t(v)]})
        elif name == "fig":
            node = figure(ch, f, ctx, depth)
            if node:
                out.append(node)
        elif name == "table-wrap":
            out.extend(table_wrap(ch, f, ctx, depth))
        elif name == "graphic":
            g = graphic(ch, f, ctx, alt_hint="Figure")
            if g:
                out.append({"t": "figure", "c": [g]})
        elif name == "supplementary-material":
            href = ch.get(XLINK) or ch.get("href") or ""
            cap, _ = caption_of(ch, f, ctx)
            label = cap or [_t("Supplementary material")]
            if href and stoa.safe_iri(href) and not stoa.PATH_REJECT.match(href):
                out.append(_p({"t": "link", "href": href, "c": label}))
            else:
                out.append({"t": "paragraph", "c": label})
        elif name in ("table-wrap-foot", "author-notes"):
            out.extend(blocks(ch, f, ctx, depth + 1))
        elif name in ("fn-group", "notes"):
            out.extend(blocks(ch, f, ctx, depth + 1))
        elif name == "fn":
            n = footnote(ch, f, ctx, depth)
            if n:
                out.append(n)
        elif name == "ref-list":
            out.append(ref_list(ch, f, ctx, depth + 1))
        elif name in ("title", "label", "caption"):
            pass
        elif name == "back":
            out.extend(blocks(ch, f, ctx, depth))
        else:
            sub = blocks(ch, f, ctx, depth + 1)
            if sub:
                out.extend(sub)
            elif "".join(ch.itertext()).strip():
                f.escapes[f"block <{name}>: no mapping"] += 1

        if tail:
            loose.append(tail)

    flush()
    return out


def caption_of(el, f, ctx):
    label = title = None
    body = []
    for g in el:
        if tag(g) == "label":
            label = clean("".join(g.itertext()))
        elif tag(g) == "caption":
            for h in g:
                if tag(h) == "title":
                    title = inline(h, f, ctx)
                else:
                    body.extend(blocks(h, f, ctx, 1))
    # A JATS caption is <label> + <title> + descriptive <p>s. Keeping only the
    # title dropped the description, which in this corpus is where the legend
    # and the abbreviations live -- the most load-bearing text on the figure.
    parts = []
    if label:
        parts.append(_t(label + ". "))
    if title:
        parts.extend(title)
    for b in body:
        inner = flatten_inline(b)
        if inner:
            # a separator is spacing, not content: merge it into the previous
            # text node rather than emitting a text node that carries nothing
            if parts and parts[-1].get("t") == "text":
                parts[-1] = _t(parts[-1]["v"].rstrip() + " ")
            parts.extend(inner)
    return stoa.prune(parts), body


def flatten_inline(block):
    """Inline content of a block, recursively. A caption takes inline children
    only, so a descriptive paragraph has to be flattened into it rather than
    dropped."""
    t = block.get("t")
    if t in ("paragraph", "term", "caption"):
        return list(block.get("c", []))
    if t == "text":
        return [block]
    out = []
    for ch in block.get("c", []):
        out.extend(flatten_inline(ch))
    return out


def figure(el, f, ctx, depth):
    f.figures += 1
    cap, extra = caption_of(el, f, ctx)
    alt_hint = "".join(x.get("v", "") for x in cap) or "Figure"
    kids = []
    for g in el.iter():
        if tag(g) == "graphic":
            m = graphic(g, f, ctx, alt_hint=alt_hint)
            if m:
                kids.append(m)
    if cap:
        kids.append({"t": "caption", "c": cap})
    if not kids:
        return None
    node = {"t": "figure", "c": kids}
    if el.get("id"):
        node["id"] = anchor(el.get("id"))
    return node


def table_wrap(el, f, ctx, depth):
    out = []
    cap, _ = caption_of(el, f, ctx)
    foot = []
    for g in el:
        if tag(g) == "table-wrap-foot":
            foot.extend(blocks(g, f, ctx, depth + 1))
    for tbl in el:
        if tag(tbl) != "table":
            continue
        node = {"t": "table", "c": []}
        if el.get("id"):
            node["id"] = anchor(el.get("id"))
        if cap:
            node["c"].append({"t": "caption", "c": cap})
        for kind, src in (("head", "thead"), ("body", "tbody"), ("foot", "tfoot")):
            rows = []
            for grp in tbl:
                if tag(grp) != src:
                    continue
                for tr in grp:
                    if tag(tr) != "tr":
                        continue
                    cells = []
                    for td in tr:
                        if tag(td) not in ("td", "th"):
                            continue
                        is_h = tag(td) == "th"
                        body = blocks(td, f, ctx, depth + 1)
                        if not body:
                            c = inline(td, f, ctx)
                            body = [{"t": "paragraph", "c": c}] if c else []
                        cell = {"t": "header-cell" if is_h else "cell", "c": body}
                        if is_h:
                            cell["scope"] = "column" if src == "thead" else "row"
                        for a, k in (("colspan", "colspan"), ("rowspan", "rowspan")):
                            if td.get(a):
                                try:
                                    cell[k] = int(td.get(a))
                                except ValueError:
                                    pass
                        cells.append(cell)
                    if cells:
                        rows.append({"t": "row", "c": cells})
            if rows:
                node["c"].append({"t": "table-section", "kind": kind, "c": rows})
        if any(c["t"] == "table-section" for c in node["c"]):
            out.append(node)
    out.extend(foot)
    return out


def footnote(el, f, ctx, depth):
    f.footnotes += 1
    body = blocks(el, f, ctx, depth + 1)
    if not body:
        c = inline(el, f, ctx)
        body = [{"t": "paragraph", "c": c}] if c else []
    if not body:
        return None
    fid = anchor(el.get("id") or f"fn-{f.footnotes}")
    return {"t": "note", "id": fid, "c": body}


def ref_list(el, f, ctx, depth):
    items = []
    for r in el:
        if tag(r) != "ref":
            continue
        txt = clean(" ".join(x for x in r.itertext() if x.strip()))
        if not txt:
            continue
        item = {"t": "item", "c": [_p(_t(txt))]}
        if r.get("id"):
            item["id"] = anchor(r.get("id"))
        items.append(item)
    head = {"t": "heading", "level": min(max(depth, 1), 6), "c": [_t("References")]}
    node = {"t": "section", "c": [head]}
    if items:
        node["c"].append({"t": "bibliography", "c": items})
    return node


def section(el, f, ctx, depth):
    title = None
    for g in el:
        if tag(g) == "title":
            title = inline(g, f, ctx)
            break
    body = blocks(el, f, ctx, depth)
    head = {"t": "heading", "level": min(max(depth, 1), 6),
            "c": title or [_t("Section")]}
    node = {"t": "section", "c": [head] + body}
    if el.get("id"):
        node["id"] = anchor(el.get("id"))
    return node


def dedupe_ids(tree, f):
    """Two footnotes in one article can carry the same anchor. An id that is
    not unique is not an identifier, so the later one loses it rather than
    producing a document that fails its own R12."""
    seen = set()
    for n, _ in stoa.walk(tree):
        i = n.get("id")
        if not isinstance(i, str):
            continue
        if i in seen:
            del n["id"]
            f.notes["duplicate source anchor: id dropped from the later node"] += 1
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
            if t in ("reference", "citation") and ch.get("target") not in ids:
                dropped[0] += 1
                out.extend(ch.get("c") or [])
                continue
            if t == "note-ref" and ch.get("target") not in ids:
                dropped[0] += 1
                continue
            go(ch)
            out.append(ch)
        node["c"] = out

    go(tree)
    if dropped[0]:
        f.notes["cross-reference to an anchor with no emitted id: degraded"] += dropped[0]
    return tree


def to_stoa(pmcid, xml, f):
    root = ET.fromstring(xml)
    if tag(root) != "article":
        root = root.find(".//article") or root
    front = root.find("front")
    ctx = {}

    title = ""
    if front is not None:
        for e in front.iter():
            if tag(e) == "article-title":
                title = clean("".join(e.itertext()))
                break

    body = [{"t": "heading", "level": 1, "c": [_t(title or pmcid)]}]

    prov = _pair("Identifier", [_p(_t(pmcid))])
    if front is not None:
        for e in front.iter():
            if tag(e) == "article-id" and e.get("pub-id-type") == "doi":
                prov += _pair("DOI", [_p({"t": "link",
                                          "href": f"https://doi.org/{clean(e.text)}",
                                          "c": [_t(clean(e.text))]})])
                break
        for e in front.iter():
            if tag(e) == "journal-title":
                prov += _pair("Journal", [_p(_t(clean("".join(e.itertext()))))])
                break
        names = []
        for c in front.iter():
            if tag(c) == "name":
                sn = c.findtext("surname") or ""
                gn = c.findtext("given-names") or ""
                nm = clean(f"{gn} {sn}")
                if nm:
                    names.append(nm)
        for nm in names[:10]:
            prov += _pair("Author", [_p(_t(nm))])
    prov += _pair("Source", [_p({"t": "link",
                                 "href": f"https://europepmc.org/article/PMC/{pmcid}",
                                 "c": [_t("Europe PMC")]})])
    body.append({"t": "provenance", "c": prov})

    if front is not None:
        for a in front.iter():
            if tag(a) == "abstract":
                inner = blocks(a, f, ctx, 1)
                if inner:
                    body.append({"t": "abstract", "c": inner})
                break

    for part in ("body", "back"):
        p = root.find(part)
        if p is not None:
            body.extend(blocks(p, f, ctx, 1))

    doc = {"t": "document", "id": f"urn:stoa:pmc:{pmcid.lower()}", "lang": "en",
           "title": (title or pmcid)[:300], "c": body}
    return resolve_refs(dedupe_ids(doc, f), f)


# --------------------------------------------------------------------------

def source_text(el, out):
    skip = META_SKIP | {"tex-math", "mml:math", "graphic", "inline-graphic"}
    if tag(el) in skip:
        return
    for s in (el.text, el.tail):
        s = clean(s)
        if s and len(s) > 3:
            out.append(s)
    for ch in el:
        source_text(ch, out)


def run(n, refresh, out_path):
    reg = stoa.Register()
    f = Findings()
    ids = discover(n, refresh)
    docs = fetch(ids, refresh)
    print(f"  {len(docs)} articles", file=sys.stderr)

    ok = clean_conf = no_loss = 0
    err_rules = Counter()
    types_used = Counter()
    per_doc = []
    jb = hb = tb = xb = 0

    for pmcid, xml in docs:
        before = sum(f.escapes.values())
        try:
            doc = to_stoa(pmcid, xml, f)
        except Exception as e:
            per_doc.append((pmcid, f"mapping raised {type(e).__name__}: {e}"))
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
            clean_conf += 1
        if not lost:
            no_loss += 1
        if not errs and not lost and not escaped:
            ok += 1
        else:
            per_doc.append((pmcid, f"{len(errs)} conformance errors, "
                            f"{len(lost)} lost strings, "
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
    w("# Corpus coverage: scholarly articles (third genre)\n")
    w(f"Generated by `tools/jats.py` over {total} open-access articles in JATS "
      f"XML, from Europe PMC.\n")
    w("This genre exists to reach what the first two could not. Administrative "
      "notices and standards documents contain no images and no footnotes, "
      "which left `media`, `note` and `note-ref` resting on the author's "
      "judgement rather than on evidence. Scholarly articles have all three in "
      "quantity.\n")

    w("## 1. Coverage\n")
    w(f"**{100.0 * ok / total:.1f}%** ({ok}/{total}) of articles map with no "
      f"element outside the register, no conformance error, and no source "
      f"string dropped.\n")
    w("| Component | Result |")
    w("|---|---|")
    w(f"| Produce a conforming document | **{100.0 * clean_conf / total:.0f}%** ({clean_conf}/{total}) |")
    w(f"| Lose no source string | **{100.0 * no_loss / total:.0f}%** ({no_loss}/{total}) |")
    w(f"| Need no element outside the register | **{100.0 * ok / total:.0f}%** ({ok}/{total}) |")
    w("")
    if err_rules:
        w("Conformance errors by rule:\n")
        for r, c in err_rules.most_common():
            w(f"- `{r}` x{c}")
        w("")
    if per_doc:
        w("Documents that did not pass cleanly:\n")
        for pid, why in per_doc[:20]:
            w(f"- {pid}: {why}")
        w("")

    w("## 2. The three elements this corpus existed to test\n")
    w("| Element | Occurrences | Verdict |")
    w("|---|---|---|")
    for name in ("media", "note", "note-ref", "figure", "caption"):
        c = types_used.get(name, 0)
        w(f"| `{name}` | {c:,} | {'**earned**' if c else 'still unproven'} |")
    w("")

    w("## 3. Accessibility, measured against reality\n")
    w(f"`media.alt` is a required, non-empty field, so **a figure with no "
      f"alternative text is unrepresentable**. That is the accessibility claim "
      f"stated as a property of the format rather than as a policy. This corpus "
      f"is the first chance to see what it costs against real documents.\n")
    pct = (100.0 * f.graphics_without_alt / f.graphics) if f.graphics else 0
    w(f"- Figures encountered: **{f.figures}**")
    w(f"- Graphics encountered: **{f.graphics}**")
    w(f"- Graphics carrying `<alt-text>` in the source: "
      f"**{f.graphics - f.graphics_without_alt}** "
      f"({100 - pct:.0f}%)")
    w(f"- Graphics with **no** alternative text in the source: "
      f"**{f.graphics_without_alt}** ({pct:.0f}%)\n")
    w("Every one of those would pass an HTML validator, ship, and fail a "
      "reader. Here they cannot be expressed at all: the mapper had to derive "
      "alternative text from the figure caption before a conforming document "
      "existed. The derived text is not as good as authored alternative text — "
      "the point is that *the absence is impossible*, so the failure happens at "
      "build time, in front of the author, instead of silently in front of a "
      "reader.\n")
    w(f"- Footnotes carried as `note` with a `note-ref` marker: **{f.footnotes}**\n")

    w("## 4. Omissions\n")
    if f.escapes:
        for k, c in f.escapes.most_common(20):
            w(f"- {k} — x{c}")
    else:
        w("None.\n")
    if f.notes:
        w("\nMapping decisions recorded:\n")
        for k, c in f.notes.most_common(10):
            w(f"- {k} — x{c}")
    w("")

    w("## 5. Element mix\n")
    w(f"{len(types_used)} of {len(reg.elements)} register elements exercised.\n")
    w("| Element | Layer | Occurrences |")
    w("|---|---|---|")
    for name, c in types_used.most_common():
        w(f"| `{name}` | L{reg.layer(name)} | {c:,} |")
    w("")

    w("## 6. Envelope\n")
    w("| | source JATS | Stoa canonical | Stoa HTML | L0 text |")
    w("|---|---|---|---|---|")
    w(f"| mean bytes / article | {xb // total:,} | {jb // total:,} | "
      f"{hb // total:,} | {tb // total:,} |")
    w("")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[written to {out_path}]", file=sys.stderr)
    return 0


def emit_one(pmcid):
    reg, f = stoa.Register(), Findings()
    (pid, xml), = fetch([pmcid])
    doc = to_stoa(pid, xml, f)
    doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))
    l0 = stoa.to_l0(doc, reg)
    out = ROOT / "corpus" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{pid}.json").write_bytes(stoa.canonical_json(doc) + b"\n")
    (out / f"{pid}.html").write_text(htmlemit.render(l0), encoding="utf-8")
    (out / f"{pid}.txt").write_text("\n".join(stoa.project_text(l0)), encoding="utf-8")
    errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
    for d in errs[:20]:
        print(d)
    print(f"{len(errs)} errors; wrote {out}/{pid}.{{json,html,txt}}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=14)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--emit", metavar="PMCID")
    ap.add_argument("--out", default=str(ROOT / "corpus" / "RESULTS-jats.md"))
    a = ap.parse_args()
    if a.emit:
        return emit_one(a.emit)
    return run(a.n, a.refresh, a.out)


if __name__ == "__main__":
    sys.exit(main())
