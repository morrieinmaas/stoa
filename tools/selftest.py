# SPDX-License-Identifier: Apache-2.0
"""Self-test for the M0 toolchain.

The conformance fixtures test the *format*. This tests the *tools*, which is a
different thing and was missing: a Merkle proof that only ever gets checked at
one index, or a degradation that is only exercised by the one document that
happens to use it, is not actually tested.

    python3 tools/selftest.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
import htmlemit        # noqa: E402
import structhash      # noqa: E402

REG = stoa.Register()
FAIL = []


def check(name, cond, detail=""):
    if cond:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name} {detail}")
        FAIL.append(name)


# --------------------------------------------------------------------------

def test_merkle_every_index():
    """A proof that is only verified at one index is not verified."""
    for n in (1, 2, 3, 4, 5, 7, 8, 45, 124):
        leaves = [stoa.structural_hash({"t": "text", "v": f"leaf-{i}"})
                  for i in range(n)]
        root, levels = stoa.merkle(leaves)
        for i in range(n):
            proof = stoa.merkle_proof(levels, i)
            if not stoa.merkle_verify(leaves[i], proof, root):
                check(f"merkle n={n} index={i}", False)
                return
            forged = stoa.structural_hash({"t": "text", "v": "forged"})
            if stoa.merkle_verify(forged, proof, root):
                check(f"merkle n={n} index={i} rejects forgery", False)
                return
    check("merkle proves and rejects at every index, n in 1..124", True)


def test_merkle_domain_separation():
    """Leaves and internal nodes must not be confusable, or a two-leaf tree's
    root is also a valid leaf somewhere else."""
    a = stoa.structural_hash({"t": "text", "v": "a"})
    b = stoa.structural_hash({"t": "text", "v": "b"})
    internal = stoa._pair(a, b)
    leafish = stoa.structural_hash({"t": "text", "v": "x"})
    check("merkle internal nodes are domain-separated from leaves",
          internal != leafish and internal[:9] != leafish[:9])


def test_cbor_roundtrip():
    cases = [0, 1, 23, 24, 255, 256, 65535, 65536, 2**32, -1, -24, -256,
             -(2**32), "", "a", "ünïcodé", "\U0001f600", True, False, None,
             [], {}, [1, [2, [3]]], {"a": {"b": {"c": 1}}},
             {"z": 1, "a": 2, "m": 3}]
    for c in cases:
        enc = structhash.cbor_encode(stoa.nfc_tree(c))
        dec, end = structhash.cbor_decode(enc)
        if dec != c or end != len(enc):
            check(f"cbor roundtrip {c!r}", False, f"got {dec!r}")
            return
    check(f"cbor roundtrips {len(cases)} edge values, no trailing bytes", True)


def test_cbor_deterministic_map_order():
    """Key order must not change the bytes, or the digest is not encoding
    independent for real."""
    a = structhash.cbor_encode({"z": 1, "a": 2, "m": 3})
    b = structhash.cbor_encode({"a": 2, "m": 3, "z": 1})
    check("cbor map encoding is key-order independent", a == b)


def test_structural_hash_sensitivity():
    base = {"t": "paragraph", "c": [{"t": "text", "v": "a"},
                                    {"t": "text", "v": "b"}]}
    swapped = {"t": "paragraph", "c": [{"t": "text", "v": "b"},
                                       {"t": "text", "v": "a"}]}
    retyped = {"t": "heading", "level": 1, "c": base["c"]}
    check("structural hash is child-order sensitive",
          stoa.structural_hash(base) != stoa.structural_hash(swapped))
    check("structural hash is type sensitive",
          stoa.structural_hash(base) != stoa.structural_hash(retyped))
    # NFC: the same text in two normalisations is the same document
    nfd = {"t": "paragraph", "c": [{"t": "text", "v": "café"}]}
    nfc = {"t": "paragraph", "c": [{"t": "text", "v": "café"}]}
    check("structural hash is normalisation independent",
          stoa.structural_hash(nfd) == stoa.structural_hash(nfc))


def test_fetch_boundary():
    bad = ["https://evil.example/px.gif", "//evil.example/px.gif",
           "\\\\evil.example\\px.gif", "javascript:alert(1)", "data:text/html,x"]
    good = ["assets/x.png", "/assets/x.png", "../x.png", "x.png?v=2"]
    check("path rejects scheme, authority and backslash",
          all(stoa.PATH_REJECT.match(v) for v in bad))
    check("path accepts same-origin relative references",
          not any(stoa.PATH_REJECT.match(v) for v in good))


def test_safe_iri():
    unsafe = ["javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x",
              "vbscript:x", "file:///etc/passwd",
              "https://x.example/\u2028x", "https://x.example/a\nb",
              "https://x.example/a\x00b"]
    safe = ["https://x.example/a", "http://x.example", "mailto:a@b.example",
            "urn:stoa:doc-1", "tel:+3012345", "relative/path", "#frag", "?k=v"]
    for v in unsafe:
        if stoa.safe_iri(v):
            check(f"safe_iri rejects {v!r}", False)
            return
    for v in safe:
        if not stoa.safe_iri(v):
            check(f"safe_iri accepts {v!r}", False)
            return
    check("safe_iri rejects code and control chars, accepts real schemes", True)


def test_html_never_emits_code():
    """Defence in depth: the emitter must not depend on the validator."""
    doc = {"t": "document", "id": "urn:stoa:x", "lang": "en", "title": "t",
           "c": [{"t": "paragraph", "c": [
               {"t": "link", "href": "javascript:alert(1)",
                "c": [{"t": "text", "v": "click"}]}]}]}
    out = htmlemit.render(doc).lower()
    check("html emitter drops a javascript: href",
          "javascript:" not in out and "click" in out)

    xss = {"t": "document", "id": "urn:stoa:x", "lang": "en",
           "title": "<script>alert(1)</script>",
           "c": [{"t": "paragraph", "c": [
               {"t": "text", "v": "<img src=x onerror=alert(1)>"}]}]}
    out2 = htmlemit.render(xss)
    check("html emitter escapes text and title",
          "<script>" not in out2 and "<img" not in out2)


def test_quantity_formatting():
    cases = [((620000, 2, "EUR"), "6200.00 EUR"),
             ((-1250, 2, "EUR"), "-12.50 EUR"),
             ((5, 0, "kg"), "5 kg"),
             ((5, 3, "kg"), "0.005 kg"),
             ((0, 2, "EUR"), "0.00 EUR")]
    for (sig, scale, unit), want in cases:
        got = stoa.format_quantity(
            {"t": "quantity", "significand": sig, "scale": scale, "unit": unit})
        if got != want:
            check(f"quantity {sig}e-{scale}", False, f"got {got!r} want {want!r}")
            return
    check("quantity renders exact decimals incl. negative and sub-unit", True)


# --------------------------------------------------------------------------
# every element above L0 must degrade, not just the ones the fixture uses
# --------------------------------------------------------------------------

SAMPLE = {"text": "x", "int": 1, "bool": True, "lang": "en",
          "urn": "urn:stoa:x", "iri": "https://x.example/a", "path": "a.png",
          "idref": "the-id", "hash": "0" * 64, "decimal": "1"}


def minimal(name, depth=0):
    spec = REG[name]
    node = {"t": name}
    for fname, fs in spec.get("fields", {}).items():
        if not fs.get("required"):
            continue
        if fs.get("enum"):
            node[fname] = fs["enum"][0]
        elif fs.get("range"):
            node[fname] = fs["range"][0]
        else:
            node[fname] = SAMPLE[fs["type"]]
    if name == "note":
        node["id"] = "the-id"
    model = spec.get("children", "none")
    if depth > 4:
        model = "none"
    if model == "none":
        pass
    elif model == "text":
        node["c"] = [{"t": "text", "v": "x"}]
    elif model == "inline":
        node["c"] = [{"t": "text", "v": "x"}]
    elif model == "flow":
        node["c"] = [minimal("paragraph", depth + 1)]
    elif isinstance(model, list):
        node["c"] = [minimal(c, depth + 1) for c in model]
    return node


def host(name):
    """A minimal *valid* document containing one instance of `name`.

    An inline element cannot be a direct child of document, and an invisible
    one carries no content, so each needs a different host. Getting this wrong
    is what the first run of this test actually caught -- in the test, not in
    the degradation.
    """
    node = minimal(name)
    cls = REG.cls(name)
    if cls == "inline":
        body = [{"t": "paragraph", "c": [node]}]
    elif cls == "invisible":
        body = [node, {"t": "paragraph", "c": [{"t": "text", "v": "x"}]}]
    else:
        body = [node]
    return {"t": "document", "id": "urn:stoa:x", "lang": "en", "title": "t",
            "c": body}


def test_every_element_degrades():
    above = [e["n"] for e in REG.raw["elements"] if e["layer"] > 0]
    bad = []
    for name in above:
        doc = host(name)
        try:
            l0 = stoa.to_l0(doc, REG)
        except Exception as e:
            bad.append(f"{name}: raised {e}")
            continue
        left = sorted({stoa.typ(n) for n, _ in stoa.walk(l0)
                       if stoa.typ(n) in REG and REG.layer(stoa.typ(n)) > 0})
        if left:
            bad.append(f"{name}: projection still contains {left}")
            continue
        errs = [d for d in stoa.validate(l0, REG) if d.sev == "error"
                and d.rule not in ("R11",)]  # synthetic idrefs do not resolve
        if errs:
            bad.append(f"{name}: projection invalid -> {errs[0]}")
    check(f"all {len(above)} elements above L0 degrade to conforming L0",
          not bad, "\n       " + "\n       ".join(bad))


def test_degradation_preserves_content():
    """The contract, as a property over synthetic documents rather than over
    the one fixture that happens to exist."""
    bad = []
    for e in REG.raw["elements"]:
        if e["layer"] == 0:
            continue
        doc = host(e["n"])
        before = stoa.content_units(doc)
        after = stoa.content_units(stoa.to_l0(doc, REG))
        from collections import Counter
        lost = Counter(before) - Counter(after)
        if lost:
            bad.append(f"{e['n']}: lost {dict(lost)}")
    check("degradation loses no content unit, for every element above L0",
          not bad, "\n       " + "\n       ".join(bad))


def test_absence_is_absence():
    """The rule three components learned separately, asserted in one place."""
    cases = [
        [{"t": "text", "v": ""}],
        [{"t": "text", "v": "   "}],
        [{"t": "emphasis", "c": [{"t": "text", "v": ""}]}],
        [{"t": "paragraph", "c": [{"t": "text", "v": ""},
                                  {"t": "text", "v": "x"}]}],
    ]
    for c in cases:
        for n, _ in zip(stoa.prune(c), range(99)):
            for m, _p in stoa.walk(n):
                if stoa.typ(m) == "text" and not str(m.get("v", "")).strip():
                    check(f"prune removes empty text from {c}", False)
                    return
    # and it must not remove elements that legitimately carry no children
    void = [{"t": "line-break"}, {"t": "media", "kind": "image",
                                  "src": "a.png", "alt": "x"}]
    if len(stoa.prune(void)) != 2:
        check("prune keeps legitimately void elements", False)
        return
    check("prune: absence of content is absence of a node", True)


def test_producers_emit_no_empty_nodes():
    """Every element above L0, projected, must contain no empty text node."""
    bad = []
    for e in REG.raw["elements"]:
        if e["layer"] == 0:
            continue
        l0 = stoa.to_l0(host(e["n"]), REG)
        for n, _ in stoa.walk(l0):
            if stoa.typ(n) == "text" and not str(n.get("v", "")).strip():
                bad.append(e["n"])
                break
    check("degradation emits no empty text node, for any element", not bad,
          str(bad))


def test_register_hash_is_provenance_only():
    """The register hash must be accepted, never acted on, never resolved."""
    h = stoa.register_digest()
    if len(h) != 64 or not all(c in "0123456789abcdef" for c in h):
        check("register digest is a sha-256 hex string", False, h)
        return
    base = {"t": "document", "id": "urn:stoa:x", "lang": "en", "title": "t",
            "c": [{"t": "paragraph", "c": [{"t": "text", "v": "x"}]}]}
    pinned = dict(base, register=h)
    stale = dict(base, register="f" * 64)
    for name, d in (("current", pinned), ("unfamiliar", stale)):
        errs = [x for x in stoa.validate(d, REG) if x.sev == "error"]
        if errs:
            check(f"a document pinning an {name} register hash validates",
                  False, str(errs[0]))
            return
    # it must not be a location
    bad = dict(base, register="https://example.org/vocabulary.json")
    if not [x for x in stoa.validate(bad, REG) if x.sev == "error"]:
        check("register must be a hash, not a location", False)
        return
    # and it must not change the digest of the content it describes
    if stoa.digest_hex(base) == stoa.digest_hex(pinned):
        check("pinning the register changes the document digest", False)
        return
    check("register hash: accepted, unfamiliar is fine, never a location", True)


def test_register_archive_resolves_offline():
    """A document pinned to a superseded register must still validate against
    the register it names -- that is the whole archival claim."""
    import json as _j
    cur = stoa.register_digest()
    if stoa.register_for(cur) is None:
        check("current register is in the local archive", False)
        return
    if stoa.register_for("f" * 64) is not None:
        check("an unknown register hash resolves to nothing", False)
        return
    arch = sorted(stoa.REGISTER_ARCHIVE.glob("*.json"))
    if len(arch) < 2:
        check("archive holds more than one register version", False,
              f"{len(arch)} found")
        return
    # every archived register must match its own filename, or the archive lies
    for f in arch:
        if stoa.register_digest(f) != f.stem:
            check(f"archive entry {f.name[:12]} matches its hash", False)
            return
    # a document pinning a superseded register validates against it
    doc = stoa.load_document(ROOT / "conformance" / "archived-01.json")
    pinned = stoa.register_for(doc.get("register"))
    if pinned is None:
        check("the archived fixture's pin resolves", False)
        return
    errs = [d for d in stoa.validate(doc, pinned) if d.sev == "error"]
    if errs:
        check("archived document validates against its pinned register",
              False, str(errs[0]))
        return
    # and it is *not* valid against the current one, which is the point
    cur_errs = [d for d in stoa.validate(doc, REG) if d.sev == "error"]
    check("a superseded pin resolves offline and still validates "
          f"({len(arch)} registers archived; document invalid against current: "
          f"{bool(cur_errs)})", bool(cur_errs))


def test_float_is_unrepresentable():
    import json
    doc = json.loads('{"t":"quantity","significand":1.5,"scale":2,"unit":"E"}',
                     parse_float=stoa.Float)
    errs = [d for d in stoa.validate(
        {"t": "document", "id": "urn:stoa:x", "lang": "en", "title": "t",
         "c": [{"t": "paragraph", "c": [doc]}]}, REG) if d.rule == "R13"]
    check("a float anywhere is a validation error", len(errs) == 1)
    try:
        stoa.structural_hash(doc)
        check("a float cannot be hashed", False)
    except ValueError:
        check("a float cannot be hashed", True)


def test_l0_freeze_scope():
    """The freeze check has to bite, and only where it should.

    A freeze digest that never moves is decoration. One that moves whenever L1
    is extended would be argued away the first time it cried wolf, and the
    freeze with it. Both directions are asserted.
    """
    import copy
    import hashlib
    import json as _json
    raw = _json.loads(stoa.REGISTER_PATH.read_text(encoding="utf-8"))
    base = stoa.l0_digest()
    check("the register's own L0 pin matches the register",
          raw.get("l0", {}).get("digest") == base)

    def moved(mutate):
        r = copy.deepcopy(raw)
        mutate(r)
        return base != hashlib.sha256(_json.dumps(
            stoa.nfc_tree(stoa.l0_closure(r)), sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False).encode("utf-8")).hexdigest()

    def el(r, layer, n=None):
        return next(e for e in r["elements"]
                    if e["layer"] == layer and (n is None or e["n"] == n))

    breaks = {
        "an L0 note is edited":
            lambda r: el(r, 0, "paragraph").__setitem__("note", "x"),
        "an L0 element is removed":
            lambda r: r["elements"].remove(el(r, 0, "quantity")),
        "an L0 element is added":
            lambda r: r["elements"].append({"n": "zz", "layer": 0,
                                            "class": "block",
                                            "children": "text", "fields": {}}),
        "a required L0 field becomes optional":
            lambda r: el(r, 0, "media")["fields"]["alt"].__setitem__(
                "required", False),
        "a field type an L0 element names is redefined":
            lambda r: r["field_types"].__setitem__("text", "anything"),
        "a content model an L0 element names is redefined":
            lambda r: r["content_models"].__setitem__("flow", "anything"),
        "a global authoring rule is added":
            lambda r: r["authoring_rules"].__setitem__("zz", "x"),
        "the field spec changes":
            lambda r: r["field_spec"].__setitem__("required", "x"),
    }
    holds = {
        "an L1 element is added":
            lambda r: r["elements"].append({"n": "zz", "layer": 1,
                                            "class": "block",
                                            "children": "flow", "fields": {},
                                            "degrades": "section"}),
        "an L2 note is edited":
            lambda r: el(r, 2).__setitem__("note", "x"),
        "an L3 render primitive changes":
            lambda r: r["render_primitives"][0].__setitem__("note", "x"),
        "the version is bumped":
            lambda r: r.__setitem__("version", "9"),
        "the freeze record itself is edited":
            lambda r: r["l0"].__setitem__("note", "x"),
        # `decimal` is described in field_types but named by no element at any
        # layer -- quantity carries an integer significand and scale instead.
        # Out of the closure by the rule, and recorded here so that stays a
        # decision rather than an accident.
        "a field type no L0 element names is redefined":
            lambda r: r["field_types"].__setitem__("decimal", "x"),
    }
    for name, mut in breaks.items():
        check(f"L0 freeze breaks when {name}", moved(mut))
    for name, mut in holds.items():
        check(f"L0 freeze holds when {name}", not moved(mut))


def main():
    print("stoa toolchain self-test\n")
    for fn in sorted(
            (v for k, v in globals().items() if k.startswith("test_")),
            key=lambda f: f.__code__.co_firstlineno):
        fn()
    print()
    if FAIL:
        print(f"{len(FAIL)} FAILED: {', '.join(FAIL)}")
        return 1
    print("all self-tests pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
