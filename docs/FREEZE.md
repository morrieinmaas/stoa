# The L0 freeze

A dated record of a decision that cannot be taken back. What was frozen, when,
on what evidence, what was knowingly accepted, and how the freeze is enforced.

This document is history. It is not amended; if it is wrong, a later record
says so.

---

## 1. The decision

On **27 August 2026**, layer **L0** of the Stoa vocabulary register was frozen
permanently.

```
L0 elements      30
frozen           2026-08-27
digest           269d4dce3149f8f2102d9d85d388bc13b162962cd21907e110f2c6e49f84f194
```

Verify with `python3 tools/stoa0.py l0freeze`, or `mise run l0freeze`. The
digest is pinned in `spec/vocabulary.json` under `l0`, and the assertion runs in
`mise run check`.

No amendment process can alter this layer. That is the load-bearing sentence in
`GOVERNANCE.md` §4, and it now has a number behind it instead of only a promise.

## 2. What the freeze covers

The digest is taken over the *closure*: the part of the register that
determines what L0 means, and nothing else.

| In | Why |
|---|---|
| The 30 L0 element records, sorted by name | The layer itself |
| The field types those records name | Redefining `text` redefines every L0 element that uses it |
| The content models those records name | Same |
| `field_spec` | It says how `required`, `enum` and `range` are read |
| `authoring_rules` | Global constraints. A new rule changes L0 without touching an L0 record |

| Out | Why |
|---|---|
| L1, L2, L3 element records | Additive-only, by design. The freeze must not obstruct them |
| `render_primitives` | L3 only |
| `counts`, `version`, `status` | Bookkeeping |
| The `l0` freeze record itself | It would not be a fixed point otherwise |
| A field type no L0 element names | Currently only `decimal`, which is described in `field_types` but named by no element at any layer — `quantity` carries an integer significand and scale instead |

The boundary is drawn by reference rather than wholesale on purpose. A freeze
check that fired every time L1 was extended would be argued away the first time
it cried wolf, and the freeze with it. `tools/selftest.py`
(`test_l0_freeze_scope`) asserts both directions: eight mutations that must move
the digest, six that must not.

## 3. The evidence at the moment of freezing

Five corpora, five genres, five markup languages, 138 documents, none of them
assembled for this project. 100% on every component of every corpus.

L0 specifically, from `spec/EVIDENCE.md`:

| Verdict | L0 elements | Meaning |
|---|---|---|
| **CORPUS** | 28 of 30 | Exercised by two or more independent genres. Through the `GOVERNANCE.md` §4.5 gate |
| **ONE GENRE** | 2 of 30 | Exercised by real documents, in one genre only |
| **FIXTURE** | 0 of 30 | — |
| **UNTESTED** | 0 of 30 | — |

Every L0 element is exercised by a document nobody wrote for this project. Two
did not clear the two-genre gate, and are frozen anyway. That is the part of
this decision that is a judgement rather than a measurement, so it is stated
plainly rather than averaged into a headline.

## 4. The two elements admitted on one genre

**`media`** — seen in JATS scholarly articles only. No other genre sampled
carries a figure: administrative notices wrap a signed PDF, RFCs are text by
tradition, forms and legislation carry neither. A second genre with figures
would very likely have been JATS-like, so the gate was unlikely to be
informative rather than merely unsatisfied. The element is also minimal —
a path, a required non-empty `alt` — and that required `alt` is the mechanism
behind the accessibility claim measured in `corpus/RESULTS-jats.md`. Freezing
it costs little and removing it would cost the claim.

**`quantity`** — seen in Diavgeia administrative notices only. This is the
weaker of the two on evidence and the stronger on design. An integer
significand with an integer scale, never a float, is load-bearing for the entire
format: it is what makes the structural digest reproducible across hosts and
what closes the encoding question. Corpus 1 tested it hard — 0 of 100 acts
needed a float, maximum observed decimal scale 2 — in the genre the format is
primarily aimed at. One genre, but the right one.

**The risk being accepted:** if either element is shaped wrongly, the remedy is
a new epoch, not a fix. Both were weighed on that basis and frozen deliberately.

## 5. What was falsified before freezing, and what was removed

The gate ran in both directions before it closed, which is the reason to
believe it was doing work rather than ratifying:

- **`power` was added.** `docs/STATE.md` §6 predicted, before any code existed,
  that superscripts were not load-bearing. The RFC corpus produced 75, every one
  an exponent, degrading to corrupted numbers inside normative text. The bet was
  written down, it was refuted with a number, and the layer had not frozen yet
  so the fix cost nothing. See `corpus/RESULTS-rfc.md`.
- **`tab-group` and `tab` were removed** when four corpora produced no instance.
- **`epigraph` was removed** when five genres produced none.

The register shrank twice and grew once under the gate.

## 6. What is *not* frozen

- **L1 and L2 are additive only**, not frozen. An element there that turns out
  unearned is recoverable; at L0 it is not. This asymmetry is why the freeze
  decision was scoped to L0 alone.
- **`contents` and `admonition` (L1)** are still exercised only by the
  conformance document. They are knowingly unearned, and they are at the layer
  where that is survivable.
- **L3 (`payload`, `rendering`) is provisional**: implementable, removable, not
  normative. No corpus of published documents can produce a typed renderer
  payload, so its gate is two independent implementations rather than two
  corpora.
- **Nothing else about this project is stable.** The tools in `tools/` are the
  throwaway M0 toolchain. There is no specification and no reference
  implementation yet. Freezing L0 fixes the floor of the format, not the
  maturity of the repository.

## 7. If L0 turns out to be wrong

A new **epoch**, coexisting with this one. Never an amendment, never a
deprecation-and-replacement inside this epoch, never an exception negotiated
into the freeze check. See design notes §9.5.

The reason to prefer an epoch to an amendment is the reason the vocabulary is
closed at all: every constrained format that died, died through its escape
hatch, and the escape hatch always opens one reasonable-sounding element at a
time.

## 8. Risks accepted, in one place

1. Two L0 elements (`media`, `quantity`) are frozen on one genre each (§4).
2. Five genres is not all genres. A sixth could need something L0 cannot
   express, and the answer would have to be an epoch or an L1 element.
3. All five corpora are Western-European or Anglophone in origin. Greek and
   English were tested; a right-to-left or CJK corpus was not.
4. The corpora were mapped by generic mappers written for this project, which
   flatters the register — `corpus/RESULTS.md` §6 states this against corpus 1.
5. The freeze precedes any real implementation. M1 may surface something the
   M0 toolchain's shape concealed.

These were known on 27 August 2026 and the layer was frozen anyway, because the
alternative — waiting for evidence that no further corpus was going to produce —
is how a format stays provisional forever.
