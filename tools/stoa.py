# SPDX-License-Identifier: Apache-2.0
"""Stoa M0 library: register, canonical form, structural hash, validator,
degradation to L0, Merkle over blocks.

Python 3 standard library only, deliberately. This is throwaway M0 scaffolding
whose job is to falsify the design before any of it is written down as
normative text. The Rust reference implementation is M1.
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTER_PATH = ROOT / "spec" / "vocabulary.json"


# --------------------------------------------------------------------------
# register
# --------------------------------------------------------------------------

class Register:
    def __init__(self, path=REGISTER_PATH):
        self.raw = json.loads(path.read_text(encoding="utf-8"))
        self.elements = {e["n"]: e for e in self.raw["elements"]}
        self.primitives = {p["n"]: p for p in self.raw["render_primitives"]}

    def __contains__(self, name):
        return isinstance(name, str) and name in self.elements

    def __getitem__(self, name):
        return self.elements[name]

    def layer(self, name):
        return self.elements[name]["layer"]

    def cls(self, name):
        return self.elements[name]["class"]

    def by_layer(self, n):
        return [e for e in self.raw["elements"] if e["layer"] == n]

    def counts(self):
        return {n: len(self.by_layer(n)) for n in (0, 1, 2, 3)}


# --------------------------------------------------------------------------
# float sentinel: a float must be unrepresentable, so we refuse to parse one
# --------------------------------------------------------------------------

class Float:
    """Marker for a JSON number that was not an integer. Never valid."""

    def __init__(self, s):
        self.s = s

    def __repr__(self):
        return f"Float({self.s})"


def load_document(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Float)


def load_json_bytes(b):
    return json.loads(b.decode("utf-8"), parse_float=Float)


# --------------------------------------------------------------------------
# node access
# --------------------------------------------------------------------------

# These four are the boundary between untrusted bytes and every other
# function here. A parser eventually eats hostile input, so they return
# something well-typed for *any* input and never raise. Malformedness is
# reported by the validator (R20), not by a traceback three calls deep.

def typ(node):
    if not isinstance(node, dict):
        return None
    t = node.get("t")
    return t if isinstance(t, str) else None


def children(node):
    """Only well-formed children, so traversal is total. Anything discarded
    here is separately reported by the validator as R20."""
    if not isinstance(node, dict):
        return []
    c = node.get("c")
    if not isinstance(c, list):
        return []
    return [x for x in c if isinstance(x, dict)]


def malformed_children(node):
    """The children that `children` had to discard."""
    if not isinstance(node, dict):
        return []
    c = node.get("c")
    if c is None:
        return []
    if not isinstance(c, list):
        return [c]
    return [x for x in c if not isinstance(x, dict)]


def fields(node):
    if not isinstance(node, dict):
        return {}
    return {k: v for k, v in node.items()
            if isinstance(k, str) and k not in ("t", "c")}


def walk(node, parent=None):
    if not isinstance(node, dict):
        return
    yield node, parent
    for ch in children(node):
        yield from walk(ch, node)


# --------------------------------------------------------------------------
# canonical form and the structural hash
#
# The digest is defined over the typed tree, not over any serialisation.
# That is what makes the encoding a revisable transport detail: canonical
# JSON and deterministic CBOR of the same document must produce the same
# digest and the same Merkle leaves.
# --------------------------------------------------------------------------

def nfc(s):
    return unicodedata.normalize("NFC", s)


def canonical_json(node):
    """Sorted keys, no insignificant whitespace, NFC, UTF-8."""
    return json.dumps(
        nfc_tree(node), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def nfc_tree(v):
    if isinstance(v, str):
        return nfc(v)
    if isinstance(v, dict):
        return {k: nfc_tree(x) for k, x in v.items()}
    if isinstance(v, list):
        return [nfc_tree(x) for x in v]
    return v


def _encode_value(v):
    if isinstance(v, bool):
        return b"true" if v else b"false"
    if isinstance(v, int):
        return str(v).encode("ascii")
    if isinstance(v, str):
        return nfc(v).encode("utf-8")
    if isinstance(v, Float):
        raise ValueError("floating point is unrepresentable in Stoa")
    raise ValueError(f"unencodable field value: {v!r}")


def structural_hash(node):
    """H(node) over the typed tree. Serialisation-independent by construction."""
    h = hashlib.sha256()
    h.update(b"stoa-node\x00")
    h.update(nfc(typ(node)).encode("utf-8") + b"\x00")
    fs = fields(node)
    h.update(b"f" + str(len(fs)).encode("ascii") + b"\x00")
    for name in sorted(fs):
        h.update(nfc(name).encode("utf-8") + b"\x00")
        h.update(_encode_value(fs[name]) + b"\x00")
    kids = children(node)
    h.update(b"c" + str(len(kids)).encode("ascii") + b"\x00")
    for ch in kids:
        h.update(structural_hash(ch))
    return h.digest()


def digest_hex(node):
    return structural_hash(node).hex()


# --------------------------------------------------------------------------
# validator
# --------------------------------------------------------------------------

PATH_REJECT = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//|\\)")

# A scheme allowlist, not a denylist. `javascript:` and `data:` are the reason:
# the format promises no author code, and an HTML projection that emits
# <a href="javascript:..."> breaks that promise at the last step. Anything not
# named here is not expressible, so the projection cannot be made to run code.
IRI_SCHEMES = ("http", "https", "mailto", "urn", "tel", "ftp", "ftps")
IRI_SCHEME = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.\-]*):")
# C0 and C1 controls, and the Unicode line/paragraph separators
CTRL = re.compile("[\\x00-\\x1f\\x7f-\\x9f\\u2028\\u2029]")
HASH_OK = re.compile(r"^[0-9a-f]{64}$")
URN_OK = re.compile(r"^urn:[a-z0-9][a-z0-9\-]{0,31}:\S+$", re.I)
LANG_OK = re.compile(r"^[a-zA-Z]{2,8}(?:-[a-zA-Z0-9]{1,8})*$")
DATE_OK = re.compile(r"^\d{4}(-\d{2}(-\d{2}(T\d{2}:\d{2}(:\d{2})?(Z|[+\-]\d{2}:\d{2})?)?)?)?$")
PAYLOAD_OK = re.compile(r"^-?\d+(?:[eE]-\d+)?(?:,-?\d+(?:[eE]-\d+)?)*$")


def safe_iri(v):
    """True if this IRI is one an emitter may put in front of a client.

    Used by the validator and, independently, by the HTML emitter. The emitter
    does not get to assume the validator ran: a projection is the last thing
    between a document and a browser.
    """
    if not isinstance(v, str) or CTRL.search(v):
        return False
    m = IRI_SCHEME.match(v)
    return not m or m.group(1).lower() in IRI_SCHEMES


class Diag:
    def __init__(self, sev, rule, where, msg):
        self.sev, self.rule, self.where, self.msg = sev, rule, where, msg

    def __str__(self):
        return f"{self.sev} [{self.rule}] {self.where}: {self.msg}"


def validate(doc, reg):
    """Return a list of Diag. Zero errors is conformance."""
    out = []
    ids = {}

    def err(rule, where, msg):
        out.append(Diag("error", rule, where, msg))

    def warn(rule, where, msg):
        out.append(Diag("warning", rule, where, msg))

    # R2: the root is a document
    if typ(doc) != "document":
        err("R2", "/", f"root must be 'document', found {typ(doc)!r}")

    def path_of(trail):
        return "/" + "/".join(trail) if trail else "/"

    MAX_DEPTH = 100

    def check(node, trail):
        where = path_of(trail)

        # R21: bounded nesting. An unbounded tree exhausts the stack of every
        # recursive consumer, and no real document needs 100 levels.
        if len(trail) > MAX_DEPTH:
            err("R21", where, f"nesting deeper than {MAX_DEPTH} levels")
            return

        # R20: the node is an object, and its children are a list of objects
        if not isinstance(node, dict):
            err("R20", where, f"node is {type(node).__name__}, not an object")
            return
        if "c" in node and not isinstance(node["c"], list):
            err("R20", where,
                f"'c' is {type(node['c']).__name__}, must be a list")
        else:
            for bad in malformed_children(node):
                err("R20", where,
                    f"child is {type(bad).__name__}, not an object")
        for k in node:
            if not isinstance(k, str):
                err("R20", where, f"field name {k!r} is not a string")
        if "t" in node and not isinstance(node["t"], str):
            err("R20", where,
                f"'t' is {type(node['t']).__name__}, must be a string")

        name = typ(node)

        # R1: known element
        if name not in reg:
            err("R1", where, f"unknown element {name!r}")
            return
        spec = reg[name]
        declared = spec.get("fields", {})
        present = fields(node)

        # R4: no unknown fields
        for f in present:
            if f not in declared:
                err("R4", where, f"unknown field {f!r} on {name}")

        for fname, fspec in declared.items():
            ftype = fspec["type"]
            required = fspec.get("required", False)
            enum = fspec.get("enum")
            rng = fspec.get("range")
            if fname not in present:
                # R3: required field present
                if required:
                    err("R3", where, f"missing required field {fname!r} on {name}")
                continue
            v = present[fname]

            # R13: no floating point, anywhere
            if isinstance(v, Float):
                err("R13", where, f"{name}.{fname} is a floating point number")
                continue

            if ftype == "int":
                if isinstance(v, bool) or not isinstance(v, int):
                    err("R5", where, f"{name}.{fname} must be an integer")
                elif rng and not (rng[0] <= v <= rng[1]):
                    err("R7", where,
                        f"{name}.{fname} = {v} outside {rng[0]}..{rng[1]}")
            elif ftype == "bool":
                if not isinstance(v, bool):
                    err("R5", where, f"{name}.{fname} must be a boolean")
            else:
                if not isinstance(v, str):
                    err("R5", where, f"{name}.{fname} must be a string")
                    continue
                # R8: a required string is non-empty
                if required and not v.strip():
                    err("R8", where, f"{name}.{fname} is empty")
                # R15: NFC
                if v != nfc(v):
                    err("R15", where, f"{name}.{fname} is not NFC-normalised")
                # R6: enum
                if enum and v not in enum:
                    err("R6", where,
                        f"{name}.{fname} = {v!r} not one of {sorted(enum)}")
                # R10: the fetch boundary
                if ftype == "path" and PATH_REJECT.match(v):
                    err("R10", where,
                        f"{name}.{fname} names a scheme or authority; a fetched "
                        f"field cannot express a host")
                # R17: no control characters in a field a client resolves
                if ftype in ("path", "iri") and CTRL.search(v):
                    err("R17", where,
                        f"{name}.{fname} contains a control character")
                if ftype == "iri":
                    m = IRI_SCHEME.match(v)
                    if m and m.group(1).lower() not in IRI_SCHEMES:
                        err("R19", where,
                            f"{name}.{fname} uses scheme {m.group(1)!r}; "
                            f"permitted: {', '.join(IRI_SCHEMES)}")
                if ftype == "hash" and not HASH_OK.match(v):
                    err("R5", where, f"{name}.{fname} is not a sha-256 hex digest")
                if ftype == "urn" and not URN_OK.match(v):
                    err("R5", where, f"{name}.{fname} is not a URN")
                if ftype == "lang" and not LANG_OK.match(v):
                    err("R5", where, f"{name}.{fname} is not a BCP 47 tag")

        # ids
        if "id" in present and isinstance(present["id"], str):
            key = present["id"]
            if key in ids:
                err("R12", where, f"duplicate id {key!r}")
            ids[key] = name

        # element-specific
        if name == "date" and isinstance(present.get("value"), str):
            if not DATE_OK.match(present["value"]):
                err("R5", where, f"date.value {present['value']!r} is not ISO 8601")
        if name == "payload" and isinstance(present.get("data"), str):
            # R14: payload data is integers and scaled decimals only
            if not PAYLOAD_OK.match(present["data"]):
                err("R14", where,
                    "payload.data must be integers or scaled decimals "
                    "(NeM-), never floats")

        # R9: content model
        model = spec.get("children", "none")
        kids = children(node)
        if model == "none":
            if kids:
                err("R9", where, f"{name} takes no children")
        elif model == "text":
            for i, ch in enumerate(kids):
                if typ(ch) != "text":
                    err("R9", f"{where}/{i}", f"{name} takes text only, found {typ(ch)!r}")
        elif model in ("inline", "flow"):
            want = "inline" if model == "inline" else "block"
            for i, ch in enumerate(kids):
                cn = typ(ch)
                if cn not in reg:
                    continue  # reported once, by the recursive check on the child
                if reg.cls(cn) not in (want, "invisible"):
                    err("R9", f"{where}/{i}",
                        f"{name} takes {want} children, {cn!r} is {reg.cls(cn)}")
        elif isinstance(model, list):
            for i, ch in enumerate(kids):
                cn = typ(ch)
                if cn not in model:
                    err("R9", f"{where}/{i}",
                        f"{name} does not permit child {cn!r}; permitted: {model}")

        # R16: structural minima
        if name in ("list", "contents", "bibliography") and not kids:
            err("R16", where, f"{name} must contain at least one item")
        if name in ("term-list", "signature-block", "provenance"):
            seq = [typ(c) for c in kids]
            if not seq or seq[0] != "term":
                err("R16", where, f"{name} must begin with a term")
            for a, b in zip(seq, seq[1:]):
                if a == "term" and b != "definition":
                    err("R16", where, "every term must be followed by a definition")
        if name == "document" and not kids:
            err("R18", where, "document is empty")

        for i, ch in enumerate(kids):
            if isinstance(ch, dict):
                check(ch, trail + [f"{i}:{typ(ch)}"])

    check(doc, [])

    # R11: intra-document references resolve
    for node, _ in walk(doc):
        if typ(node) in ("reference", "note-ref", "citation", "rendering"):
            key = "payload" if typ(node) == "rendering" else "target"
            tgt = node.get(key)
            if isinstance(tgt, str) and tgt not in ids:
                err("R11", f"/{typ(node)}", f"reference target {tgt!r} does not exist")

    return out


# --------------------------------------------------------------------------
# content units and the degradation contract
#
# A content unit is anything that produces reader-visible characters. The
# contract is that projecting to L0 loses none of them.
# --------------------------------------------------------------------------

FIELD_UNITS = {
    "media": ["alt"],
    "submit": ["label"],
    "field": ["label"],
    "disclosure": ["summary"],
    "tab": ["label"],
    "rendering": ["fallback"],
    "admonition": ["kind"],
    "quote": ["source"],
    "epigraph": ["source"],
    "caption": [],
}


def content_units(doc):
    units = []
    for node, _ in walk(doc):
        name = typ(node)
        if name == "text":
            units.append(nfc(str(node.get("v", ""))))
        elif name == "quantity":
            units.append(format_quantity(node))
        elif name == "power":
            units.append(format_power(node))
        elif name == "date":
            units.append(str(node.get("value", "")))
        for f in FIELD_UNITS.get(name, []):
            v = node.get(f)
            if isinstance(v, str) and v.strip():
                units.append(nfc(v))
    return units


def format_power(node):
    return f"{node.get('base', '')}^{node.get('exponent', '')}"


def format_quantity(node):
    sig, scale = node.get("significand", 0), node.get("scale", 0)
    unit = node.get("unit", "")
    neg = sig < 0
    d = str(abs(sig)).rjust(scale + 1, "0")
    s = d if scale == 0 else f"{d[:-scale]}.{d[-scale:]}"
    return f"{'-' if neg else ''}{s} {unit}".strip()


# --------------------------------------------------------------------------
# degradation to L0
# --------------------------------------------------------------------------

def _text(s):
    return {"t": "text", "v": s}


def _para(s):
    # an empty string is absence of content, not a text node carrying nothing;
    # emitting the latter makes the projection fail its own R8 check
    return {"t": "paragraph", "c": [_text(s)] if s else []}


def to_l0(node, reg):
    """Project any conforming document into the L0 subset.

    Every element above L0 has a normative degradation. This function is the
    executable form of that promise, and `contract` asserts it loses nothing.
    """
    name = typ(node)
    kids = []
    for ch in children(node):
        r = to_l0(ch, reg)
        if r is None:
            continue
        kids.extend(r if isinstance(r, list) else [r])

    if name not in reg or reg.layer(name) == 0:
        out = dict(fields(node))
        out["t"] = name
        if kids:
            out["c"] = kids
        return out

    f = fields(node)

    if name in ("article", "abstract", "sidebar"):
        return {"t": "section", "c": kids}
    if name in ("contents", "bibliography"):
        return {"t": "list", "ordered": name == "contents", "c": kids}
    if name == "citation":
        return {"t": "reference", "target": f["target"], "c": kids}
    if name == "admonition":
        head = {"t": "heading", "level": 3, "c": [_text(f["kind"])]}
        return {"t": "section", "c": [head] + kids}
    if name == "epigraph":
        out = {"t": "quote", "c": kids}
        if f.get("source"):
            out["source"] = f["source"]
        return out
    if name in ("signature-block", "provenance"):
        return {"t": "term-list", "c": kids}
    if name == "table-section":
        return kids  # spliced into the parent table, in order
    if name == "form":
        return {"t": "section", "c": _group_term_pairs(kids)}
    if name == "field":
        return [{"t": "term", "c": [_text(f["label"])]},
                {"t": "definition", "c": kids or [_para("")]}]
    if name == "field-text":
        return _para(f.get("value", ""))
    if name == "field-choice":
        return {"t": "list", "ordered": False, "c": kids}
    if name == "field-option":
        return {"t": "item", "c": [{"t": "paragraph", "c": kids}]}
    if name == "submit":
        return _para(f["label"])
    if name == "disclosure":
        head = {"t": "heading", "level": 3, "c": [_text(f["summary"])]}
        return {"t": "section", "c": [head] + kids}
    if name == "tab-group":
        return {"t": "section", "c": kids}
    if name == "tab":
        head = {"t": "heading", "level": 3, "c": [_text(f["label"])]}
        return {"t": "section", "c": [head] + kids}
    if name == "state-link":
        return {"t": "link", "href": f"?{f['key']}={f['value']}", "c": kids}
    if name == "payload":
        return None  # carries no visible content
    if name == "rendering":
        return {"t": "figure",
                "c": kids + [{"t": "caption", "c": [_text(f["fallback"])]}]}

    raise ValueError(f"no degradation defined for {name!r}")


def _group_term_pairs(kids):
    """Wrap consecutive term/definition children in a term-list so that a
    degraded form is itself conforming L0."""
    out, run = [], []
    for k in kids:
        if typ(k) in ("term", "definition"):
            run.append(k)
        else:
            if run:
                out.append({"t": "term-list", "c": run})
                run = []
            out.append(k)
    if run:
        out.append({"t": "term-list", "c": run})
    return out


# --------------------------------------------------------------------------
# L0 text projection
# --------------------------------------------------------------------------

INLINE = {"text", "emphasis", "strong", "code", "link", "reference",
          "note-ref", "quantity", "power", "date", "line-break"}


def inline_text(node):
    name = typ(node)
    if name == "text":
        return nfc(str(node.get("v", "")))
    if name == "quantity":
        return format_quantity(node)
    if name == "power":
        return format_power(node)
    if name == "date":
        return str(node.get("value", ""))
    if name == "line-break":
        return "\n"
    if name == "note-ref":
        return f"[{node.get('target')}]"
    inner = "".join(inline_text(c) for c in children(node))
    if name == "code":
        return f"`{inner}`"
    if name == "link":
        return f"{inner} <{node.get('href')}>"
    return inner


def _indent(lines, prefix):
    """Prefix each line, including lines produced by an inline line-break."""
    for b in lines:
        if not b.strip():
            continue
        for part in b.split("\n"):
            yield prefix + part


def project_text(node, out=None):
    """Deterministic plain-text rendering of an L0 tree. This is the golden
    output, and it is also what a terminal or speech client sees."""
    if out is None:
        out = []
    name = typ(node)

    if name == "document":
        out.append(node["title"])
        out.append("=" * len(node["title"]))
        out.append("")
        for c in children(node):
            project_text(c, out)
    elif name == "section":
        for c in children(node):
            project_text(c, out)
    elif name == "heading":
        t = inline_text(node)
        out.append(("#" * min(node.get("level", 1), 6)) + " " + t)
        out.append("")
    elif name == "paragraph":
        out.append(inline_text(node))
        out.append("")
    elif name == "list":
        for i, it in enumerate(children(node), start=node.get("start", 1)):
            marker = f"{i}." if node.get("ordered") else "-"
            body = []
            for c in children(it):
                project_text(c, body)
            body = [b for b in body if b.strip()]
            if body:
                first = body[0].split("\n")
                out.append(f"{marker} {first[0]}")
                out.extend(_indent(first[1:] + body[1:], "  "))
        out.append("")
    elif name == "term-list":
        for c in children(node):
            if typ(c) == "term":
                out.append(inline_text(c) + ":")
            else:
                body = []
                for g in children(c):
                    project_text(g, body)
                out.extend(_indent(body, "  "))
        out.append("")
    elif name == "quote":
        body = []
        for c in children(node):
            project_text(c, body)
        out.extend(_indent(body, "> "))
        if node.get("source"):
            out.append(f"> -- {node['source']}")
        out.append("")
    elif name == "code-block":
        out.append("```" + (node.get("language") or ""))
        out.extend("".join(inline_text(c) for c in children(node)).split("\n"))
        out.append("```")
        out.append("")
    elif name == "note":
        body = []
        for c in children(node):
            project_text(c, body)
        out.append(f"[{node.get('id')}] " + " ".join(b for b in body if b.strip()))
        out.append("")
    elif name == "figure":
        for c in children(node):
            project_text(c, out)
    elif name == "caption":
        out.append("(" + inline_text(node) + ")")
        out.append("")
    elif name == "media":
        out.append(f"[{node.get('kind')}: {node.get('alt')}]")
        out.append("")
    elif name == "table":
        if node.get("summary"):
            out.append(f"[table: {node['summary']}]")
        for r in children(node):
            if typ(r) != "row":
                project_text(r, out)
                continue
            cells = []
            for c in children(r):
                body = []
                for g in children(c):
                    project_text(g, body)
                cells.append(" ".join(b for b in body if b.strip()))
            out.append(" | ".join(cells))
        out.append("")
    elif name in ("item", "cell", "header-cell", "term", "definition"):
        for c in children(node):
            project_text(c, out)
    elif name in INLINE:
        out.append(inline_text(node))
    else:
        for c in children(node):
            project_text(c, out)
    return out


# --------------------------------------------------------------------------
# Merkle over block nodes
# --------------------------------------------------------------------------

def block_nodes(doc, reg):
    return [n for n, _ in walk(doc)
            if typ(n) in reg and reg.cls(typ(n)) == "block"]


def _pair(a, b):
    return hashlib.sha256(b"stoa-merkle\x00" + a + b).digest()


def merkle(leaves):
    """Returns (root, levels). Odd nodes are promoted, not duplicated, which
    avoids the CVE-2012-2459 style duplicate-leaf forgery."""
    if not leaves:
        return hashlib.sha256(b"stoa-merkle-empty").digest(), []
    levels = [list(leaves)]
    cur = list(leaves)
    while len(cur) > 1:
        nxt = []
        for i in range(0, len(cur) - 1, 2):
            nxt.append(_pair(cur[i], cur[i + 1]))
        if len(cur) % 2:
            nxt.append(cur[-1])
        levels.append(nxt)
        cur = nxt
    return cur[0], levels


def merkle_proof(levels, index):
    """Sibling path for a leaf. A quoted paragraph becomes independently
    provable without transmitting the document."""
    proof = []
    idx = index
    for level in levels[:-1]:
        if idx % 2 == 0:
            if idx + 1 < len(level):
                proof.append(("R", level[idx + 1]))
        else:
            proof.append(("L", level[idx - 1]))
        idx //= 2
    return proof


def merkle_verify(leaf, proof, root):
    h = leaf
    for side, sib in proof:
        h = _pair(sib, h) if side == "L" else _pair(h, sib)
    return h == root
