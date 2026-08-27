# SPDX-License-Identifier: Apache-2.0
"""stoa0 -- the M0 command line.

    python3 tools/stoa0.py <document.json> <command>

Commands:
    canon      canonical form, byte count, structural digest
    check      run the conformance ruleset
    contract   project to L0 and assert no content unit is lost
    merkle     Merkle root over block nodes, plus one excerpt proof
    provenance check the document against the register it claims, offline
    l0         emit the L0 text projection
    project    emit the degraded L0 tree as canonical JSON
    all        canon, check, contract, merkle
    register   (no document) print the vocabulary register as markdown
    registerhash (no document) print the register's own content hash
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa  # noqa: E402


def cmd_canon(doc, reg):
    b = stoa.canonical_json(doc)
    print(f"canonical bytes  {len(b)}")
    print(f"structural hash  {stoa.digest_hex(doc)}")
    used = {stoa.typ(n) for n, _ in stoa.walk(doc) if stoa.typ(n) in reg}
    total = len(reg.elements)
    print(f"distinct types   {len(used)} of {total} in register")
    missing = sorted(set(reg.elements) - used)
    if missing:
        print(f"not exercised    {', '.join(missing)}")
    return 0


def cmd_check(doc, reg):
    diags = stoa.validate(doc, reg)
    for d in diags:
        print(d)
    errs = sum(1 for d in diags if d.sev == "error")
    warns = sum(1 for d in diags if d.sev == "warning")
    print(f"check            {errs} errors, {warns} warnings")
    return 1 if errs else 0


def cmd_contract(doc, reg):
    before = stoa.content_units(doc)
    l0 = stoa.to_l0(doc, reg)
    after = stoa.content_units(l0)

    from collections import Counter
    missing = Counter(before) - Counter(after)
    lost = sum(missing.values())

    # the projection must itself be conforming L0
    diags = stoa.validate(l0, reg)
    errs = [d for d in diags if d.sev == "error"]
    above = sorted({stoa.typ(n) for n, _ in stoa.walk(l0)
                    if stoa.typ(n) in reg and reg.layer(stoa.typ(n)) > 0})

    print(f"contract         {len(before)} units checked, "
          f"{lost} lost in projection to L0")
    if missing:
        for u, k in list(missing.items())[:10]:
            print(f"  lost x{k}: {u[:60]!r}")
    if above:
        print(f"  projection still contains non-L0 elements: {above}")
    if errs:
        print(f"  projection is not conforming L0: {len(errs)} errors")
        for d in errs[:10]:
            print(f"    {d}")
    return 1 if (lost or above or errs) else 0


def cmd_merkle(doc, reg):
    blocks = stoa.block_nodes(doc, reg)
    leaves = [stoa.structural_hash(b) for b in blocks]
    root, levels = stoa.merkle(leaves)
    idx = len(leaves) // 2
    proof = stoa.merkle_proof(levels, idx)
    ok = stoa.merkle_verify(leaves[idx], proof, root)

    tampered = stoa.merkle_verify(
        stoa.structural_hash({"t": "paragraph", "c": [{"t": "text", "v": "forged"}]}),
        proof, root)

    print(f"merkle root      {root.hex()}")
    print(f"merkle blocks    {len(leaves)}   proof size {len(proof)} sibling "
          f"hashes ({len(proof) * 32} bytes)   verifies {ok}")
    print(f"tamper check     forged leaf verifies {tampered} (must be False)")
    return 0 if (ok and not tampered) else 1


def cmd_provenance(doc, reg):
    """Check a document against the register it claims, not the current one.

    This is what makes `document.register` more than decoration: a document
    archived in 2026 and read in 2036 can be validated against the vocabulary
    it was actually written against, offline, without trusting that the reader
    happens to hold the right one.
    """
    claimed = doc.get("register")
    current = stoa.register_digest()
    print(f"document digest  {stoa.digest_hex(doc)}")
    print(f"register claimed {claimed or '(none — the document does not pin one)'}")
    print(f"register current {current}")

    if not claimed:
        errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
        print(f"validated against current register: {len(errs)} errors")
        print("note             an unpinned document is conforming, but its "
              "conformance claim is only meaningful with out-of-band knowledge "
              "of which vocabulary was current when it was written")
        return 1 if errs else 0

    if claimed == current:
        errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
        print(f"pin              matches the current register")
        print(f"validated        {len(errs)} errors")
        return 1 if errs else 0

    pinned = stoa.register_for(claimed)
    if pinned is None:
        print("pin              NOT RESOLVABLE from the local archive")
        print("                 the client does not fetch it: a hash is not a "
              "location, and resolving one would breach the fetch boundary")
        errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
        print(f"validated against the current register instead: {len(errs)} errors")
        print("note             this document may legitimately use elements "
              "added or removed since; treat the result as advisory")
        return 0

    errs = [d for d in stoa.validate(doc, pinned) if d.sev == "error"]
    cur_errs = [d for d in stoa.validate(doc, reg) if d.sev == "error"]
    print(f"pin              resolved from the local archive "
          f"({len(pinned.elements)} elements)")
    print(f"validated against the pinned register:  {len(errs)} errors")
    print(f"validated against the current register: {len(cur_errs)} errors")
    if errs and not cur_errs:
        print("reading          the document is valid now but was not valid "
              "against the register it claims: the pin is wrong")
    if cur_errs and not errs:
        print("reading          the document was valid when written and uses "
              "something the current register no longer has. This is what an "
              "epoch is for; it is not a defect in the document")
    return 1 if errs else 0


def cmd_l0(doc, reg):
    l0 = stoa.to_l0(doc, reg)
    print("\n".join(stoa.project_text(l0)).rstrip())
    return 0


def cmd_project(doc, reg):
    l0 = stoa.to_l0(doc, reg)
    sys.stdout.buffer.write(stoa.canonical_json(l0) + b"\n")
    return 0


def cmd_all(doc, reg):
    rc = 0
    for fn in (cmd_canon, cmd_check, cmd_contract, cmd_merkle):
        rc |= fn(doc, reg)
    return rc


def cmd_register(reg):
    r = reg.raw
    print("<!-- generated by tools/stoa0.py register; edit spec/vocabulary.json -->")
    print("# Vocabulary register\n")
    print(f"Register `{r['register']}`, version `{r['version']}`.\n")
    print(f"**Status:** {r['status']}\n")
    c = reg.counts()
    print(f"{c[0]} elements at L0, {c[1]} at L1, {c[2]} at L2, {c[3]} at L3. "
          f"Total {sum(c.values())}, plus {len(reg.primitives)} render "
          f"primitives that are not document elements.\n")
    print("A document element above L0 declares the element it degrades into. "
          "That declaration is normative and mechanically tested: "
          "`stoa0.py <doc> contract` projects the whole document to L0 and "
          "asserts that no unit of reader-visible content is lost.\n")
    print("L0 is therefore not a reduced or lossy view. It is the layer every "
          "other layer is defined against, and the projection into it is "
          "normative output rather than best-effort extraction. Any consumer "
          "that wants meaning without presentation reads it directly: a screen "
          "reader, a terminal client, an archival indexer, or an autonomous "
          "agent. Those are one consumer with one guarantee, which is why "
          "non-visual targets are siblings in this design rather than "
          "accommodations.\n")

    if r.get("authoring_rules"):
        print("## Rules for producers\n")
        print("These bind anything that emits a conforming tree: a degradation "
              "projection, an importer from another format, a surface parser. "
              "Each was independently rediscovered by more than one component "
              "during M0, which is why they are stated here rather than left "
              "to each implementer.\n")
        for k, v in r["authoring_rules"].items():
            print(f"**`{k}`** — {v}\n")

    print("## Field types\n")
    for k, v in r["field_types"].items():
        print(f"- `{k}` — {v}")
    print()

    layer_names = {0: "L0 — content", 1: "L1 — structure",
                   2: "L2 — interaction", 3: "L3 — typed rendering"}
    for layer in (0, 1, 2, 3):
        print(f"## {layer_names[layer]}\n")
        if layer == 0:
            pin = reg.raw.get("l0", {})
            if pin.get("frozen"):
                print(f"**Frozen {pin['frozen']}.** No amendment process can "
                      "alter this layer; if L0 is wrong the answer is a new "
                      "epoch, never a change to this one. The freeze covers "
                      "these records and the definitions they rest on, at "
                      f"content hash `{pin['digest']}`, asserted by "
                      "`mise run l0freeze`. Record: `docs/FREEZE.md`.\n")
            else:
                print("Frozen on release. No amendment process can alter this "
                      "layer; if L0 is wrong the answer is a new epoch, never "
                      "a change to this one.\n")
        print("| Element | Class | Children | Degrades to | Fields |")
        print("|---|---|---|---|---|")
        for e in reg.by_layer(layer):
            model = e.get("children", "none")
            model = "`" + (", ".join(model) if isinstance(model, list)
                           else model) + "`"
            parts = []
            for k, v in e.get("fields", {}).items():
                s = f"`{k}`{'' if v.get('required') else '?'}:{v['type']}"
                if v.get("enum"):
                    s += " ∈ {" + ", ".join(v["enum"]) + "}"
                if v.get("range"):
                    s += f" [{v['range'][0]}..{v['range'][1]}]"
                parts.append(s)
            fs = ", ".join(parts) or "—"
            deg = f"`{e['degrades']}`" if e.get("degrades") else "—"
            print(f"| `{e['n']}` | {e['class']} | {model} | {deg} | {fs} |")
        print()
        notes = [e for e in reg.by_layer(layer) if e.get("note")]
        if notes:
            print("Notes:\n")
            for e in notes:
                print(f"- **`{e['n']}`** — {e['note']}")
            print()

    print("## Render primitives\n")
    print("Not document elements and not part of the 52. These are what an "
          "L3 renderer emits into a device-independent display list. Text "
          "emitted by a renderer stays text.\n")
    print("| Primitive | Fields |")
    print("|---|---|")
    for p in reg.raw["render_primitives"]:
        fs = ", ".join(f"`{k}`:{v}" for k, v in p["fields"].items())
        print(f"| `{p['n']}` | {fs} |")
    return 0


def cmd_l0freeze(reg):
    """Assert that frozen L0 has not moved."""
    actual = stoa.l0_digest()
    pin = reg.raw.get("l0", {})
    n = sum(1 for e in reg.raw["elements"] if e["layer"] == 0)
    print(f"L0 elements      {n}")
    print(f"frozen           {pin.get('frozen', '-- NOT FROZEN --')}")
    print(f"pinned digest    {pin.get('digest', '--')}")
    print(f"computed digest  {actual}")
    if not pin.get("digest"):
        print("L0 FREEZE        no pin in the register")
        return 1
    ok = pin["digest"] == actual
    print(f"L0 FREEZE        {'intact' if ok else 'BROKEN'}")
    if not ok:
        print("\nL0 is frozen permanently: docs/FREEZE.md, and the load-bearing")
        print("sentence in docs/GOVERNANCE.md section 4. This digest changing means an")
        print("L0 element, a field type or content model an L0 element names, the field")
        print("spec, or a global authoring rule has moved. The remedy is a new epoch")
        print("coexisting with this one, never an edit to this one.")
    return 0 if ok else 1


def cmd_registerhash(reg):
    print(stoa.register_digest())
    return 0


COMMANDS = {"canon": cmd_canon, "check": cmd_check, "contract": cmd_contract,
            "merkle": cmd_merkle, "l0": cmd_l0, "project": cmd_project,
            "provenance": cmd_provenance, "all": cmd_all}


def main(argv):
    reg = stoa.Register()
    if len(argv) >= 2 and argv[1] == "register":
        return cmd_register(reg)
    if len(argv) >= 2 and argv[1] == "registerhash":
        return cmd_registerhash(reg)
    if len(argv) >= 2 and argv[1] == "l0freeze":
        return cmd_l0freeze(reg)
    if len(argv) < 3 or argv[2] not in COMMANDS:
        print(__doc__)
        return 2
    doc = stoa.load_document(argv[1])
    return COMMANDS[argv[2]](doc, reg)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
