# Stoa

A hypermedia document format and conformance profile, transported over
unmodified HTTPS.

Not a protocol, not a browser, not an alternative internet. The closest
structural analogue is PDF/A: a constrained format defined by what it
guarantees rather than by what it can express.

**Status:** M0 and M0b complete. Design notes, a closed vocabulary register, a
working throwaway toolchain, and two corpus coverage runs against real public
documents in two genres. The second corpus falsified one of the design's stated
bets, which is what it was for. Not a specification, not a reference
implementation. Nothing here is stable, and **L0 is not frozen** — see below.

---

## What this is

A document format with a finite semantic vocabulary of **50 elements**,
delivered over ordinary HTTPS, where the document carries meaning and structure
and never carries appearance. Presentation comes from themes written against
the vocabulary rather than against any individual site, and reader preferences
override publisher styling with no mechanism for the publisher to override
back.

The client fetches content and nothing else: no scripts, no stylesheets per
document, no font files, no third-party subresources. A document cannot name a
host that the client will contact without the reader acting, so third-party
requests are *unrepresentable* rather than forbidden.

Four conformance layers. Every layer degrades in band to the one below, so a
client implementing only L0 obtains the complete meaning of any conforming
document, including documents published years after that client shipped. That
single property does double duty as the accessibility guarantee and as the
forward-compatibility mechanism.

## What this is not

Not a replacement for the web. Not an application platform. Not a way to render
existing web pages. Applications are a separate resource type that a document
may link to and can never contain.

## Why

Two audiences, one mechanism: a document that carries meaning and never
appearance is simultaneously the one a screen reader can read and the one a
machine does not have to guess at. Accessibility and machine consumption are the
same property seen from two ends, and both are measured in this repository
rather than asserted.

Four claims that are hard to make anywhere else, all mechanically checkable
rather than asserted:

- **Accessibility by construction.** Structural failures are unrepresentable,
  and the mechanically detectable content failures are build errors. A sampled
  recurring audit becomes a complete build-time check.
- **Verifiable content.** The document digest is defined over the tree rather
  than over any serialisation, so it is signable, and a Merkle construction over
  block nodes makes individual paragraphs independently provable without
  transmitting the document.
- **Bounded, declared rendering cost.** A line a procurement officer can put in
  a tender.
- **Meaning is emitted, not recovered.** Because a document carries structure
  and never appearance, any consumer that wants meaning without presentation —
  a screen reader, a terminal client, an archival indexer, an autonomous agent —
  reads the normative L0 projection instead of inferring structure from a
  rendering. This is the same mechanism as the accessibility claim, measured
  from the other end; see [Machine and agent consumption](#machine-and-agent-consumption).

---

## Measured, not claimed

Every number below is produced by the toolchain in this repository. Reproduce
them with `mise run check` and `mise run corpora`.

### The conformance document

```
canonical bytes  9436
structural hash  8541efc87f9014c543ad515e8a3bdd445a315e65d803f2801c4710da5511a27e
distinct types   50 of 50 in register
check            0 errors, 0 warnings
contract         91 units checked, 0 lost in projection to L0
merkle blocks    118   proof size 7 sibling hashes (224 bytes)   verifies True
tamper check     forged leaf verifies False (must be False)
ENCODING INDEPENDENT True
```

- All 50 elements are exercised by one document.
- The negative fixture carries 13 deliberate faults across 13 distinct rules,
  and the ruleset reports exactly 13 errors. Asserted in CI.
- The degradation contract is verified mechanically: every unit of
  reader-visible content survives projection to L0, and the projection is
  itself conforming L0.
- Canonical JSON and deterministic CBOR of the same document produce an
  identical digest and identical Merkle leaves, so the encoding is a revisable
  transport detail rather than part of the format.
- A 118-block document yields a 224-byte excerpt proof. One quoted paragraph is
  provable without transmitting the document, and a forged block fails.
- 19 toolchain self-tests: Merkle proof and forgery rejection at *every* index
  for n = 1..124, CBOR edge cases and key-order determinism, injection, and
  degradation totality over synthetic instances of all 23 elements above L0.
- 5,000 generated hostile documents per fuzz run, 0 crashes. The first run
  found 272 in 3,000 — see `m0/FINDINGS.md` defect 12.

### Corpus 1: administrative notices

100 real published acts from [Diavgeia](https://diavgeia.gov.gr), the Greek
national transparency register (~3.1M acts), sampled across 10 act types and 66
public bodies. Full report in [`corpus/RESULTS.md`](corpus/RESULTS.md).

| | Result |
|---|---|
| Coverage | **100%** (100/100) map with no element outside the register, no conformance error, and no source string dropped |
| Elements needed but missing | **0** |
| Amounts requiring a float | **0** — maximum decimal scale observed is 2 |
| Source text not NFC-normalised | 0/100 |

Envelope, against the live Diavgeia page for the same act:

| | Live page | Stoa HTML projection |
|---|---|---|
| HTML bytes | 22,187 | **2,143** (mean) |
| Fetched subresources | 80 | **0** |
| Requests to first complete content | 81 | **1** |

The subresource count is not a minification result. It is what the vocabulary
makes expressible.

### Machine and agent consumption

The same act, from the point of view of a consumer that wants the meaning and
not the page:

| | Live page | Stoa L0 text projection |
|---|---|---|
| Bytes to ingest | 22,187 | **1,361** |
| Of which recoverable text | 2,235 (10%) | 1,361 (100%) |
| Markup and boilerplate paid for but unusable | 19,952 (**89%**) | **0** |
| | | **16.3× smaller** |

A screen reader, a terminal client, an archival indexer and an autonomous agent
are the same consumer under this design. All four want structure without
presentation, and the L0 projection is normative and guaranteed lossless by the
degradation contract rather than being a best-effort extraction.

Today a machine reader ingests a presentation layer and infers structure from
it, paying ~89% of its budget for markup it cannot use and inheriting every
ambiguity of that inference. Here the structure is declared, so there is no
inference step — and because a block node is Merkle-provable, a cited paragraph
is *verifiable* rather than merely quoted. Non-visual consumption is a
first-class target, not an accommodation, which is also why the terminal client
in `docs/ROADMAP.md` is a conformance proof rather than a nicety.

**Read the 100% with its caveats.** `corpus/RESULTS.md` section 6 states them:
the act body is a signed PDF that this does not test, a generic mapper flatters
the register, the corpus is one genre in one language, and 32 of the 50
elements were never exercised. This corpus is a falsifier that did not fire —
which is exactly why a second one was needed.

---

## Running the toolchain

Python 3, standard library only, no dependencies.

```sh
python3 tools/stoa0.py conformance/conformance-01.json all   # canon, check, contract, merkle
python3 tools/stoa0.py conformance/negative-01.json check    # must report 13 errors
python3 tools/stoa0.py conformance/conformance-01.json l0    # the L0 text projection
python3 tools/structhash.py conformance/conformance-01.json  # encoding independence
python3 tools/stoa0.py register                              # regenerate spec/VOCABULARY.md
```

The corpus test, which reaches the network on first run and caches afterwards:

```sh
python3 tools/diavgeia.py --n 100              # coverage report -> corpus/RESULTS.md
python3 tools/diavgeia.py --n 100 --refresh    # refetch the corpus
python3 tools/diavgeia.py --emit <ADA>         # one notice as canonical JSON, HTML and text
```

Or with [`mise`](https://mise.jdx.dev):

```sh
mise run check     # everything offline, and fails loudly if it should not
mise run corpora   # all three corpus runs, plus the evidence audit
mise run fuzz      # 5000 hostile documents
mise run golden    # regenerate the golden output and the generated spec
```

## Layout

```
spec/vocabulary.json          the register: normative, machine-readable
spec/VOCABULARY.md            generated from it; do not edit by hand
conformance/                  the conformance document, negative fixture, golden output
tools/                        throwaway M0 toolchain (Python, standard library only)
corpus/RESULTS.md             corpus 1: administrative notices (Diavgeia)
corpus/RESULTS-rfc.md         corpus 2: standards documents (IETF RFCs)
corpus/RESULTS-jats.md        corpus 3: scholarly articles (JATS)
spec/EVIDENCE.md              what justifies each element; generated
design/design-notes.md        the working design document
corpus/sample/                one real notice as canonical JSON, HTML and text
m0/FINDINGS.md                what closing the vocabulary actually surfaced
docs/STATE.md                 where things stand, what is next, funding position
docs/GOVERNANCE.md            licensing, custody, amendment process, succession
docs/ROADMAP.md               milestones
docs/FUNDING.md               the funding application
docs/LICENSING.md             licence split and rationale
docs/NAME.md                  naming decision and how to undo it
```

### The second corpus, and what it falsified

16 IETF RFCs in RFC 7991 XML v3 — standards documents in English, the opposite
genre from Greek administrative notices on every axis that matters. Full report
in [`corpus/RESULTS-rfc.md`](corpus/RESULTS-rfc.md).

| | Corpus 1 (Diavgeia) | Corpus 2 (RFCs) |
|---|---|---|
| Produce a conforming document | 100% | **100%** |
| Lose no source string | 100% | 81% |
| Need no element outside the register | 100% | **44%** |
| Register elements exercised | 20 of 53 | **31 of 53** |

**It found a real hole.** `<sup>` occurs 75 times, and every occurrence is an
exponent: `2^64`, `2^32`, `2^62`. The register has no superscript, so those
degrade to `264` and `232` — inside sentences of the form *"an integer in the
range -2^64..2^64-1 inclusive"*. That is not a formatting loss, it is silent
numeric corruption in a normative range specification, produced by a format
whose entire numeric thesis is exactness.

`docs/STATE.md` §6 explicitly bet that superscripts would not be load-bearing.
That bet is now falsified, with a number attached. See
[`m0/FINDINGS.md`](m0/FINDINGS.md) defect 8 for the three candidate fixes.

### Corpus 3: scholarly articles, and the accessibility claim measured

14 open-access articles in JATS XML from Europe PMC — the genre the first two
could not reach, because neither administrative notices nor RFCs contain an
image or a footnote. Full report in
[`corpus/RESULTS-jats.md`](corpus/RESULTS-jats.md).

| | Result |
|---|---|
| Produce a conforming document | **100%** (14/14) |
| Lose no source string | **100%** (14/14) |
| Need no element outside the register | **100%** (14/14) |
| `media` / `note` / `note-ref` occurrences | 65 / 48 / 32 — all three **earned** |

**The accessibility claim, measured against reality.** `media.alt` is a
required, non-empty field, so a figure with no alternative text is
*unrepresentable*. In this corpus:

- 65 graphics encountered
- **0 of 65 (0%)** carried alternative text in the source
- **65 of 65 (100%)** had none

Every one of those would pass an HTML validator, ship, and fail a reader. Here
they cannot be expressed at all — the mapper had to derive alternative text from
the figure caption before a conforming document existed. Derived text is worse
than authored text; the point is that *the absence is impossible*, so the
failure surfaces at build time in front of the author instead of silently in
front of a reader.

### Is the register earned?

`spec/EVIDENCE.md`, generated by `mise run evidence`, classifies all 53
elements by what justifies them:

| Verdict | Count | Meaning |
|---|---|---|
| **CORPUS** | 37 | Exercised by real documents nobody wrote for this project |
| **BY DESIGN** | 12 | L2/L3 — no corpus of published static documents can contain a form or a renderer payload |
| **FIXTURE** | 4 | L1 only, exercised solely by the conformance document |
| **UNTESTED** | 0 | — |

**Every L0 element is now backed by real documents.** L0 is the layer that
freezes permanently, so it is the layer where an unearned element is unfixable.

## The one thing standing between here and freezing L0

Nothing mechanical. Three corpora across three genres are at 100% on every
component, every L0 element is corpus-backed, and the one bet that was
falsified (superscripts) has been fixed by adding `power`.

What is left is a judgement call, not a measurement: four L1 elements
(`article`, `contents`, `admonition`, `epigraph`) are still exercised only by
the conformance document. L1 is additive-only rather than frozen, so an
unearned element there is recoverable — unlike at L0. The freeze is a decision
the maintainer should now take deliberately rather than a task waiting on
evidence. See `spec/EVIDENCE.md` and `docs/STATE.md`.

## Licensing

Split three ways, all irrevocable, all permitting independent implementation
without permission.

| Path | Licence |
|---|---|
| `spec/`, `docs/`, `m0/`, `*.md` | `CC-BY-4.0` |
| `conformance/`, `corpus/` | `CC0-1.0` |
| `tools/`, all future implementation code | `Apache-2.0` |

No patent claims are asserted over the format, the canonical encoding, the
structural hash, or any conformant implementation, and none will be.
Implementation is royalty-free and unconditional. Full texts in `LICENSES/`.
See `docs/LICENSING.md` and `docs/GOVERNANCE.md`.
