# SPDX-License-Identifier: Apache-2.0
"""Second corpus, second genre: IETF RFCs in RFC 7991 XML v3.

The first corpus (`diavgeia.py`) is administrative notices: shallow records in
Greek, structured metadata around a signed PDF. It did not falsify the
vocabulary and it never exercised 32 of the 52 elements. One genre is not
evidence that a closed vocabulary is closed correctly.

This is the opposite genre on every axis that matters: standards prose in
English, deeply nested sections, an abstract, a table of contents, numbered
lists, definition lists, source code, figures, tables, cross-references, a
bibliography with citations, and editorial notes.

It is also chosen because it can *fail*. RFC XML has `sup`, `sub` and `iref`,
which the register deliberately does not have -- `../docs/STATE.md` section 6
asks in as many words whether superscripts turn out to be load-bearing in
practice, and bets they are not. This measures the bet instead of restating it.

    python3 tools/rfc.py                 # 12 RFCs, cached
    python3 tools/rfc.py --n 20 --refresh
    python3 tools/rfc.py --emit 9110     # one RFC as canonical JSON, HTML, text
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
except Exception:  # pragma: no cover - interpreter build without pyexpat
    sys.stderr.write(
        "this Python has no pyexpat, so it cannot parse XML.\n"
        "Use the pinned interpreter:  mise run corpus-rfc\n")
    raise SystemExit(2)
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402
import htmlemit        # noqa: E402
import structhash      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "corpus" / "cache" / "rfc"

# A spread of genres inside the genre: core protocol specs, a BCP, an
# informational document, a format specification, and a process document.
# Only RFCs published from the XML v3 era have machine-readable source; the
# older ones exist as text only, which is a different (and much weaker) test.
DEFAULT_RFCS = [9110, 9111, 9112, 9113, 9114, 8949, 9000, 9204,
                9205, 9293, 9297, 9421, 9457, 9562, 8890, 8942]

# RFC XML v3 elements that carry no reader-visible content of their own.
SKIP = {"iref", "toc", "xi:include"}

# Elements whose content is metadata we lift into provenance rather than prose.
FRONT_SKIP = {"title", "author", "date", "area", "workgroup", "keyword",
              "abstract", "note", "boilerplate", "seriesInfo"}

# Author identity and postal details. RFC XML repeats these in <back>; they are
# provenance, not prose, and emitting them inline would put a postal address in
# the middle of a specification.
AUTHOR_META = {"author", "address", "postal", "postalLine", "street", "city",
               "region", "code", "country", "email", "phone", "uri",
               "organization", "seriesInfo", "boilerplate"}


def _get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "stoa-corpus/0"})
    with urllib.request.urlopen(req, timeout=90) as f:
        return f.read()


def fetch(numbers, refresh=False):
    CACHE.mkdir(parents=True, exist_ok=True)
    out = []
    for n in numbers:
        p = CACHE / f"rfc{n}.xml"
        if not p.exists() or refresh:
            try:
                p.write_bytes(_get(f"https://www.rfc-editor.org/rfc/rfc{n}.xml"))
                time.sleep(0.4)
            except urllib.error.URLError as e:
                print(f"  rfc{n}: fetch failed {e}", file=sys.stderr)
                continue
        out.append((n, p.read_bytes()))
    return out


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------

def _t(s):
    return {"t": "text", "v": s}


def _p(*c):
    return {"t": "paragraph", "c": list(c)}


def _pair(k, blocks):
    return [{"t": "term", "c": [_t(k)]}, {"t": "definition", "c": blocks}]


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


class Findings:
    def __init__(self):
        self.escapes = Counter()
        self.notes = Counter()
        self.src_elements = Counter()


def tag(el):
    return el.tag.split("}")[-1]


# --------------------------------------------------------------------------
# inline
# --------------------------------------------------------------------------

INLINE_MAP = {"strong": "strong", "em": "emphasis", "tt": "code",
              "bcp14": "strong", "u": "emphasis", "spanx": "emphasis"}

# RFC XML permits these directly inside <dd>, <li>, <td> and <blockquote>,
# where a block context is expected. Treating them as blocks was the first
# real defect this corpus surfaced.
INLINE_TAGS = set(INLINE_MAP) | {"xref", "relref", "eref", "br", "sup", "sub",
                                 "cref", "contact", "iref"}



BASE_TOKEN = re.compile(r"([A-Za-z0-9]+)$")


def inline_one(ch, f, anchors, prev=None):
    """One RFC inline element -> zero or more Stoa inline nodes.

    `prev` is the list built so far, because <sup> needs the token before it:
    in `2<sup>64</sup>` the base lives in the preceding text node's tail.
    """
    name = tag(ch)
    kids = inline(ch, f, anchors)

    if name in INLINE_MAP:
        return [{"t": INLINE_MAP[name], "c": kids}] if kids else []
    if name in ("xref", "relref"):
        target = ch.get("target", "")
        label = kids or [_t(target)]
        # a reference into the bibliography is a citation, into the body a
        # cross-reference. Both stay inside the document, so neither fetches.
        kind = "citation" if target in anchors.get("refs", ()) else "reference"
        return [{"t": kind, "target": _anchor(target), "c": label}]
    if name == "eref":
        href = ch.get("target", "")
        if stoa.safe_iri(href):
            return [{"t": "link", "href": href, "c": kids or [_t(href)]}]
        f.escapes[f"eref with unusable scheme: {href[:40]}"] += 1
        return kids
    if name == "br":
        return [{"t": "line-break"}]
    if name == "sup":
        # Every superscript in this corpus is an exponent, which is why L0
        # gained `power`. Take the base from the preceding text node so that
        # 2<sup>64</sup> becomes one semantic node rather than two fragments.
        exp = clean("".join(ch.itertext()))
        if exp and prev and prev[-1].get("t") == "text":
            m = BASE_TOKEN.search(prev[-1]["v"])
            if m:
                prev[-1]["v"] = prev[-1]["v"][:m.start()]
                if not prev[-1]["v"]:
                    prev.pop()
                return [{"t": "power", "base": m.group(1), "exponent": exp}]
        f.escapes["<sup> with no adjacent base token"] += 1
        return kids or ([_t(exp)] if exp else [])
    if name == "sub":
        # Subscripts do not occur in this corpus. Recorded if they ever do.
        f.escapes["<sub>: no element in the register"] += 1
        return kids or ([_t(clean(ch.text))] if clean(ch.text) else [])
    if name == "contact":
        # a person, inline. Their name is the content; the rest is metadata
        # that belongs in provenance, not mid-sentence.
        n = clean(ch.get("fullname") or ch.get("surname") or "")
        return [_t(n)] if n else kids
    if name == "cref":
        return kids
    if name in SKIP:
        return []
    f.escapes[f"inline <{name}>: no mapping"] += 1
    return kids


def inline(el, f, anchors):
    """RFC mixed content -> Stoa inline nodes."""
    out = []
    if el.text and el.text.strip():
        out.append(_t(clean(el.text)))
    for ch in el:
        f.src_elements[tag(ch)] += 1
        out.extend(inline_one(ch, f, anchors, out))
        if ch.tail and ch.tail.strip():
            out.append(_t(clean(ch.tail)))
    return stoa.prune(out)


def _anchor(a):
    return re.sub(r"[^A-Za-z0-9_.:-]", "-", a or "x") or "x"


# --------------------------------------------------------------------------
# blocks
# --------------------------------------------------------------------------

def blocks(el, f, anchors, depth=0):
    out = []
    loose = []

    def flush():
        """Loose inline content in a block slot becomes a paragraph, rather
        than being dropped as an unmappable block."""
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
            loose.extend(inline_one(ch, f, anchors, loose))
            if ch.tail and ch.tail.strip():
                loose.append(_t(clean(ch.tail)))
            continue

        flush()
        if ch.tail and ch.tail.strip():
            tail = _t(clean(ch.tail))
        else:
            tail = None

        if name in SKIP or (name in FRONT_SKIP and depth == 0):
            if tail:
                loose.append(tail)
            continue

        if name == "t":
            c = inline(ch, f, anchors)
            if c:
                out.append({"t": "paragraph", "c": c})
        elif name in ("ul", "ol"):
            items = []
            for li in ch:
                if tag(li) != "li":
                    continue
                body = blocks(li, f, anchors, depth + 1)
                if not body and clean(li.text):
                    body = [_p(_t(clean(li.text)))]
                items.append({"t": "item", "c": body})
            if items:
                node = {"t": "list", "ordered": name == "ol", "c": items}
                if name == "ol" and ch.get("start"):
                    try:
                        node["start"] = int(ch.get("start"))
                    except ValueError:
                        pass
                out.append(node)
        elif name == "dl":
            pairs, pending = [], None
            for d in ch:
                if tag(d) == "dt":
                    # consecutive <dt> without a <dd>: the earlier term is
                    # still content and must not be overwritten
                    if pending:
                        pairs += [{"t": "term", "c": pending},
                                  {"t": "definition", "c": []}]
                    pending = inline(d, f, anchors)
                elif tag(d) == "dd":
                    body = blocks(d, f, anchors, depth + 1)
                    if not body:
                        c = inline(d, f, anchors)
                        body = [{"t": "paragraph", "c": c}] if c else []
                    if not pending:
                        # <dt/> with content in its <dd>: a continuation of the
                        # previous definition, not a new pair. Skipping it here
                        # silently dropped whole paragraphs.
                        if pairs and body:
                            pairs[-1]["c"].extend(body)
                        elif body:
                            pairs += [{"t": "term", "c": []},
                                      {"t": "definition", "c": body}]
                        continue
                    # A term whose definition is empty still carries the term.
                    # Dropping the pair loses the term text, which is content.
                    pairs += [{"t": "term", "c": pending},
                              {"t": "definition", "c": body}]
                    pending = None
            if pending:
                pairs += [{"t": "term", "c": pending},
                          {"t": "definition", "c": []}]
            if pairs:
                out.append({"t": "term-list", "c": pairs})
        elif name in ("sourcecode", "artwork"):
            txt = "".join(ch.itertext())
            if txt.strip():
                node = {"t": "code-block", "c": [_t(txt)]}
                if ch.get("type"):
                    node["language"] = ch.get("type")
                out.append(node)
        elif name == "blockquote":
            body = blocks(ch, f, anchors, depth + 1)
            if body:
                node = {"t": "quote", "c": body}
                if ch.get("quotedFrom"):
                    node["source"] = clean(ch.get("quotedFrom"))
                out.append(node)
        elif name == "aside":
            body = blocks(ch, f, anchors, depth + 1)
            if body:
                out.append({"t": "sidebar", "c": body})
        elif name == "cref":
            body = blocks(ch, f, anchors, depth + 1)
            if not body:
                c = inline(ch, f, anchors)
                body = [{"t": "paragraph", "c": c}] if c else []
            if body:
                out.append({"t": "admonition", "kind": "note", "c": body})
        elif name == "figure":
            inner, cap = [], None
            for g in ch:
                if tag(g) == "name":
                    cap = inline(g, f, anchors)
                else:
                    inner += blocks_one(g, f, anchors, depth + 1)
            fig = [b for b in inner if b["t"] in ("media", "table", "code-block")]
            rest = [b for b in inner if b not in fig]
            if fig:
                node = {"t": "figure", "c": fig}
                if cap:
                    node["c"].append({"t": "caption", "c": cap})
                out.append(node)
            out.extend(rest)
        elif name == "table":
            out.append(table(ch, f, anchors, depth))
        elif name == "section":
            out.append(section(ch, f, anchors, depth + 1))
        elif name == "references":
            out.append(references(ch, f, anchors, depth + 1))
        elif name == "name":
            pass
        elif name in AUTHOR_META:
            # Author postal addresses and contact details are front matter that
            # RFC XML repeats in <back>. They belong in provenance, and mapping
            # them as prose would put a postal address mid-document.
            pass
        else:
            sub = blocks(ch, f, anchors, depth + 1)
            if sub:
                out.extend(sub)
            elif "".join(ch.itertext()).strip():
                f.escapes[f"block <{name}>: no mapping"] += 1

        if tail:
            loose.append(tail)

    flush()
    return out


def blocks_one(el, f, anchors, depth):
    holder = ET.Element("holder")
    holder.append(el)
    return blocks(holder, f, anchors, depth)


def table(el, f, anchors, depth):
    node = {"t": "table", "c": []}
    for g in el:
        if tag(g) == "name":
            cap = inline(g, f, anchors)
            if cap:
                node["c"].append({"t": "caption", "c": cap})
    for kind, src in (("head", "thead"), ("body", "tbody"), ("foot", "tfoot")):
        rows = []
        for grp in el:
            if tag(grp) != src:
                continue
            for tr in grp:
                if tag(tr) != "tr":
                    continue
                cells = []
                for td in tr:
                    is_h = tag(td) == "th"
                    body = blocks(td, f, anchors, depth + 1)
                    if not body:
                        c = inline(td, f, anchors)
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
    if not any(c["t"] == "table-section" for c in node["c"]):
        node["c"].append({"t": "table-section", "kind": "body",
                          "c": [{"t": "row", "c": [{"t": "cell", "c": []}]}]})
        f.notes["table with no rows"] += 1
    return node


def section(el, f, anchors, depth):
    name = None
    for g in el:
        if tag(g) == "name":
            name = inline(g, f, anchors)
            break
    body = blocks(el, f, anchors, depth)
    head = [{"t": "heading", "level": min(max(depth, 1), 6),
             "c": name or [_t("Section")]}]
    node = {"t": "section", "c": head + body}
    if el.get("anchor"):
        node["id"] = _anchor(el.get("anchor"))
    return node


def references(el, f, anchors, depth):
    items = []
    for r in el:
        if tag(r) == "references":
            items += [{"t": "item", "c": [x] }
                      for x in [references(r, f, anchors, depth + 1)]]
            continue
        if tag(r) != "reference":
            continue
        bits = []
        for fr in r.iter():
            if tag(fr) == "title" and clean(fr.text):
                bits.append(clean(fr.text))
        target = r.get("target")
        c = [_t("; ".join(bits) or r.get("anchor", "reference"))]
        if target and stoa.safe_iri(target):
            c = [{"t": "link", "href": target, "c": c}]
        item = {"t": "item", "c": [{"t": "paragraph", "c": c}]}
        if r.get("anchor"):
            item["id"] = _anchor(r.get("anchor"))
        items.append(item)
    name = None
    for g in el:
        if tag(g) == "name":
            name = inline(g, f, anchors)
            break
    head = {"t": "heading", "level": min(max(depth, 1), 6),
            "c": name or [_t("References")]}
    node = {"t": "section", "c": [head]}
    if el.get("anchor"):
        node["id"] = _anchor(el.get("anchor"))
    if items:
        node["c"].append({"t": "bibliography", "c": items})
    return node


# --------------------------------------------------------------------------

def to_stoa(num, xml, f):
    root = ET.fromstring(xml)
    front = root.find("front")
    back = root.find("back")

    # anchors that live in the bibliography, so xref can pick citation vs reference
    refs = set()
    if back is not None:
        for r in back.iter():
            if tag(r) == "reference" and r.get("anchor"):
                refs.add(r.get("anchor"))
    anchors = {"refs": refs}

    title = clean(front.findtext("title")) if front is not None else f"RFC {num}"
    body = [{"t": "heading", "level": 1, "c": [_t(title)]}]

    prov = _pair("Document", [_p(_t(f"RFC {num}"))])
    if root.get("category"):
        prov += _pair("Category", [_p(_t(root.get("category")))])
    if front is not None:
        d = front.find("date")
        if d is not None and d.get("year"):
            v = d.get("year")
            if d.get("month"):
                prov += _pair("Date", [_p(_t(f"{d.get('month')} {v}"))])
            else:
                prov += _pair("Date", [_p({"t": "date", "value": v,
                                           "precision": "year"})])
        names = [clean(a.findtext("./author/name") or a.get("fullname") or "")
                 for a in front.findall("author")]
        names = [n for n in names if n]
        for n in names[:8]:
            prov += _pair("Author", [_p(_t(n))])
    prov += _pair("Source", [_p({"t": "link",
                                 "href": f"https://www.rfc-editor.org/rfc/rfc{num}",
                                 "c": [_t(f"rfc-editor.org/rfc/rfc{num}")]})])
    body.append({"t": "provenance", "c": prov})

    if front is not None:
        ab = front.find("abstract")
        if ab is not None:
            inner = blocks(ab, f, anchors, 1)
            if inner:
                body.append({"t": "abstract", "c": inner})
        for nt in front.findall("note"):
            inner = blocks(nt, f, anchors, 1)
            if inner:
                body.append({"t": "admonition", "kind": "note", "c": inner})

    for part in ("middle", "back"):
        p = root.find(part)
        if p is not None:
            body.extend(blocks(p, f, anchors, 1))

    doc = {"t": "document", "id": f"urn:stoa:rfc:{num}", "lang": "en",
           "title": title[:300] or f"RFC {num}", "c": body}
    return resolve_refs(doc, f)


# --------------------------------------------------------------------------

def resolve_refs(tree, f):
    """A cross-reference whose target is not in the emitted document degrades
    to its own label.

    RFC XML anchors far more than this mapping emits ids for -- individual
    paragraphs, list items, IANA registry rows. Emitting a reference to a node
    that is not there would be a dangling pointer dressed up as a citation,
    which is worse than plain text. This is the intra-document form of the same
    rule as the fetch boundary: a document may not name what is not there.
    """
    ids = {n["id"] for n, _ in stoa.walk(tree)
           if isinstance(n.get("id"), str)}
    dropped = [0]

    def go(node):
        kids = node.get("c")
        if not kids:
            return
        out = []
        for ch in kids:
            if stoa.typ(ch) in ("reference", "citation") \
                    and ch.get("target") not in ids:
                dropped[0] += 1
                out.extend(ch.get("c") or [])
                continue
            go(ch)
            out.append(ch)
        node["c"] = out

    go(tree)
    if dropped[0]:
        f.notes["cross-reference to an anchor this mapping does not emit "
                "an id for: degraded to its label"] += dropped[0]
    return tree


def source_text(el, out):
    """Every reader-visible string in the source, for the no-loss check.

    Author postal details and front-matter metadata are excluded because the
    mapping deliberately lifts them into provenance rather than prose. That is
    a decision on the record, declared here, not an accident."""
    skip = AUTHOR_META | {"artwork", "sourcecode", "date", "seriesInfo",
                          "keyword", "area", "workgroup", "title", "reference",
                          "toc"}
    if tag(el) in skip:
        return
    for s in (el.text, el.tail):
        s = clean(s)
        if s and len(s) > 3:
            out.append(s)
    for ch in el:
        source_text(ch, out)


def run(nums, refresh, out_path):
    reg = stoa.Register()
    f = Findings()
    docs = fetch(nums, refresh)
    print(f"  {len(docs)} RFCs", file=sys.stderr)

    ok = clean_conf = no_loss = 0
    err_rules = Counter()
    types_used = Counter()
    per_doc = []
    jb = cb = hb = tb = xb = 0

    for num, xml in docs:
        before = sum(f.escapes.values())
        try:
            doc = to_stoa(num, xml, f)
        except Exception as e:
            per_doc.append((num, f"mapping raised {type(e).__name__}: {e}", 0))
            continue
        doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))

        diags = stoa.validate(doc, reg)
        errs = [d for d in diags if d.sev == "error"]
        for d in errs:
            err_rules[d.rule] += 1

        want = []
        source_text(ET.fromstring(xml), want)
        carried = set(stoa.content_units(doc))
        # Compare against the rendered L0 projection, not against the set of
        # content units. A unit boundary is not a text boundary: `power` takes
        # its base from the preceding text node, so "range -2" spans two units
        # and only the projection puts it back together.
        blob = re.sub(r"\s+", " ",
                      "\n".join(stoa.project_text(stoa.to_l0(doc, reg))))
        lost = [s for s in want
                if s not in carried
                and re.sub(r"\s+", " ", s) not in blob]

        escaped = sum(f.escapes.values()) > before
        if not errs:
            clean_conf += 1
        if not lost:
            no_loss += 1
        if not errs and not lost and not escaped:
            ok += 1
        else:
            per_doc.append((num, f"{len(errs)} conformance errors, "
                            f"{len(lost)} lost strings, "
                            f"{'needs an element outside the register' if escaped else 'no omission'}",
                            len(lost)))

        for node, _ in stoa.walk(doc):
            if stoa.typ(node) in reg:
                types_used[stoa.typ(node)] += 1

        l0 = stoa.to_l0(doc, reg)
        jb += len(stoa.canonical_json(doc))
        cb += len(structhash.cbor_encode(stoa.nfc_tree(doc)))
        hb += len(htmlemit.render(l0).encode("utf-8"))
        tb += len("\n".join(stoa.project_text(l0)).encode("utf-8"))
        xb += len(xml)

    total = len(docs) or 1
    cov = 100.0 * ok / total

    w = [].append
    lines = []
    w = lines.append
    w("# Corpus coverage: IETF RFCs (second genre)\n")
    w(f"Generated by `tools/rfc.py` over {total} RFCs in RFC 7991 XML v3.\n")
    w("The first corpus is administrative notices in Greek: shallow records "
      "wrapped around a signed PDF. This is the opposite genre on every axis "
      "that matters -- standards prose in English, deeply nested sections, "
      "abstracts, definition lists, source code, figures, tables, "
      "cross-references and bibliographies. It exists to reach what the first "
      "corpus could not, and to be capable of failing.\n")

    w("## 1. Coverage\n")
    w(f"**{cov:.1f}%** ({ok}/{total}) of RFCs map with no element outside the "
      f"register, no conformance error, and no source string dropped. That "
      f"headline is strict on purpose; the three components differ and the "
      f"difference is the finding.\n")
    w(f"| Component | Result |")
    w(f"|---|---|")
    w(f"| Produce a conforming document | **{100.0 * clean_conf / total:.0f}%** "
      f"({clean_conf}/{total}) |")
    w(f"| Lose no source string | **{100.0 * no_loss / total:.0f}%** "
      f"({no_loss}/{total}) |")
    w(f"| Need no element outside the register | **{100.0 * ok / total:.0f}%** "
      f"({ok}/{total}) |")
    w("")
    if err_rules:
        w("Conformance errors by rule:\n")
        for r, c in err_rules.most_common():
            w(f"- `{r}` x{c}")
        w("")
    if per_doc:
        w("Documents that did not pass cleanly:\n")
        for num, why, _ in per_doc[:20]:
            w(f"- RFC {num}: {why}")
        w("")

    w("## 2. Omissions -- what the register could not carry\n")
    if f.escapes:
        w("This is the finding the corpus exists to produce.\n")
        for k, c in f.escapes.most_common(25):
            w(f"- {k} — x{c}")
        w("")
    else:
        w("None.\n")

    w("## 3. Element mix\n")
    w(f"{len(types_used)} of {len(reg.elements)} register elements exercised "
      f"by this genre.\n")
    w("| Element | Layer | Occurrences |")
    w("|---|---|---|")
    for name, c in types_used.most_common():
        w(f"| `{name}` | L{reg.layer(name)} | {c:,} |")
    w("")
    unused = sorted(set(reg.elements) - set(types_used))
    w(f"Not exercised here ({len(unused)}): "
      f"{', '.join('`' + u + '`' for u in unused)}.\n")

    w("## 4. Envelope\n")
    w("| | source XML | Stoa canonical | Stoa CBOR | Stoa HTML | L0 text |")
    w("|---|---|---|---|---|---|")
    w(f"| mean bytes / RFC | {xb // total:,} | {jb // total:,} | "
      f"{cb // total:,} | {hb // total:,} | {tb // total:,} |")
    w("")

    w("## 5. Source elements seen\n")
    w("What RFC XML actually used, so the mapping can be audited:\n")
    w("| RFC XML element | Occurrences |")
    w("|---|---|")
    for k, c in f.src_elements.most_common(30):
        w(f"| `{k}` | {c:,} |")
    w("")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[written to {out_path}]", file=sys.stderr)
    return 0


def emit_one(num):
    reg, f = stoa.Register(), Findings()
    (num, xml), = fetch([int(num)])
    doc = to_stoa(int(num), xml, f)
    doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))
    l0 = stoa.to_l0(doc, reg)
    out = ROOT / "corpus" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"rfc{num}.json").write_bytes(stoa.canonical_json(doc) + b"\n")
    (out / f"rfc{num}.html").write_text(htmlemit.render(l0), encoding="utf-8")
    (out / f"rfc{num}.txt").write_text("\n".join(stoa.project_text(l0)),
                                       encoding="utf-8")
    errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
    for d in errs[:20]:
        print(d)
    print(f"{len(errs)} errors; wrote {out}/rfc{num}.{{json,html,txt}}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=len(DEFAULT_RFCS))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--emit", metavar="NUM")
    ap.add_argument("--out", default=str(ROOT / "corpus" / "RESULTS-rfc.md"))
    a = ap.parse_args()
    if a.emit:
        return emit_one(a.emit)
    return run(DEFAULT_RFCS[:a.n], a.refresh, a.out)


if __name__ == "__main__":
    sys.exit(main())
