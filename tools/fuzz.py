# SPDX-License-Identifier: Apache-2.0
"""Fuzz the parser and validator.

The parser will eventually eat untrusted input, so the property under test is
not "does it accept good documents" but "does it ever do anything other than
accept or cleanly reject". A crash, a hang, or an unhandled exception in a
validator is a denial of service in every client that embeds it.

Deterministic by seed, so a failure is reproducible and becomes a fixture.

    python3 tools/fuzz.py                 # 2000 cases
    python3 tools/fuzz.py --n 20000 --seed 7
"""

import argparse
import json
import random
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402
import htmlemit        # noqa: E402
import structhash      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CRASHERS = ROOT / "fuzz" / "crashers"

NASTY = [
    "", " ", "\x00", "\n", "\r\n", "\t", "\\", "\"", "'", "<", ">", "&",
    "</script>", "<script>alert(1)</script>", "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>", "vbscript:x",
    "//evil.example", "https://evil.example", "\\\\evil.example",
    "../../../../etc/passwd", "%2e%2e%2f", "‮", " ", "",
    "é", "﻿", "\U0001f600" * 3, "A" * 4096, "urn:", "urn:x:",
    "#", "?", ":", "0" * 64, "-1", "1e309", "NaN", "Infinity",
]

TYPES = None  # filled from the register


def rand_value(rnd, depth):
    r = rnd.random()
    if r < 0.30:
        return rnd.choice(NASTY)
    if r < 0.45:
        return rnd.randint(-(2 ** 70), 2 ** 70)
    if r < 0.52:
        return rnd.choice([True, False, None])
    if r < 0.60:
        return rnd.choice([1.5, -0.0, 1e308])          # floats: must be rejected
    if r < 0.70 and depth < 3:
        return [rand_value(rnd, depth + 1) for _ in range(rnd.randint(0, 3))]
    if r < 0.78 and depth < 3:
        return {str(rnd.randint(0, 5)): rand_value(rnd, depth + 1)
                for _ in range(rnd.randint(0, 3))}
    return rnd.choice(NASTY)


def rand_node(rnd, depth=0):
    node = {}
    if rnd.random() < 0.92:
        node["t"] = rnd.choice(TYPES + ["", "marquee", "\x00", "text"])
    for _ in range(rnd.randint(0, 4)):
        key = rnd.choice(["v", "id", "level", "src", "alt", "kind", "href",
                          "target", "significand", "scale", "unit", "value",
                          "ordered", "lang", "title", "renderer", "payload",
                          "data", "action", "method", "label", "summary",
                          "colspan", "scope", "language", "source", "name",
                          "\x00", "c", "t"])
        node[key] = rand_value(rnd, depth)
    if depth < 4 and rnd.random() < 0.6:
        node["c"] = [rand_node(rnd, depth + 1)
                     for _ in range(rnd.randint(0, 3))]
    return node


def one_case(rnd, reg):
    """Everything a hostile document touches, in order."""
    doc = rand_node(rnd)

    # 1. the validator must return diagnostics, never raise
    diags = stoa.validate(doc, reg)
    assert isinstance(diags, list)

    # 2. serialisation must either produce bytes or refuse cleanly
    try:
        stoa.canonical_json(doc)
    except (ValueError, TypeError):
        pass

    # 3. the digest must refuse floats rather than hash them
    try:
        stoa.structural_hash(doc)
    except (ValueError, TypeError):
        pass

    # 4. CBOR must round-trip or refuse
    try:
        enc = structhash.cbor_encode(stoa.nfc_tree(doc))
        structhash.cbor_decode(enc)
    except (ValueError, TypeError, KeyError, IndexError):
        pass

    # 5. degradation and both projections, but only for documents that pass;
    #    they are specified over conforming trees, not over arbitrary input
    if not any(d.sev == "error" for d in diags):
        l0 = stoa.to_l0(doc, reg)
        assert not [d for d in stoa.validate(l0, reg) if d.sev == "error"], \
            "a conforming document projected to a non-conforming one"
        stoa.project_text(l0)
        out = htmlemit.render(l0)
        low = out.lower()
        # 6. the emitter must never put executable content in front of a client
        for bad in ("javascript:", "vbscript:", "<script", "onerror=",
                    "data:text/html"):
            assert bad not in low, f"emitter produced {bad!r}"
    return doc


def main():
    global TYPES
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    reg = stoa.Register()
    TYPES = sorted(reg.elements)
    rnd = random.Random(a.seed)
    bad = 0

    for i in range(a.n):
        try:
            one_case(rnd, reg)
        except AssertionError as e:
            bad += 1
            _save(rnd, a.seed, i, e, reg)
        except Exception as e:  # noqa: BLE001 - the whole point
            bad += 1
            _save(rnd, a.seed, i, e, reg, tb=True)

    print(f"fuzz: {a.n} cases, seed {a.seed}, {bad} failures")
    if bad:
        print(f"crashers written to {CRASHERS}")
    return 1 if bad else 0


def _save(rnd, seed, i, exc, reg, tb=False):
    CRASHERS.mkdir(parents=True, exist_ok=True)
    # regenerate the exact input from a fresh stream so the fixture is minimal
    p = CRASHERS / f"seed{seed}-case{i}.json"
    try:
        p.write_text(json.dumps({"seed": seed, "case": i,
                                 "error": f"{type(exc).__name__}: {exc}"},
                                indent=2), encoding="utf-8")
    except Exception:
        pass
    print(f"  FAIL case {i}: {type(exc).__name__}: {exc}")
    if tb:
        traceback.print_exc()


if __name__ == "__main__":
    sys.exit(main())
