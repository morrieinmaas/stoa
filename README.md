# Stoa

A hypermedia document format and conformance profile, transported over
unmodified HTTPS.

Not a protocol, not a browser, not an alternative internet. The closest
structural analogue is PDF/A: a constrained format defined by what it
guarantees rather than by what it can express.

**Status:** M0 complete, and **L0 was frozen on 27 August 2026** — permanently,
enforced by a content hash that `mise run check` asserts. A closed vocabulary
register, design notes, a working throwaway toolchain, and five corpus coverage
runs over 138 real public documents in five genres. One of those corpora
falsified a bet the design had written down, which is what it was for. Not a
specification, not a reference implementation: freezing L0 fixes the floor of
the format, not the maturity of this repository. The freeze record, including
the risks knowingly accepted, is [`docs/FREEZE.md`](docs/FREEZE.md).

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

## Why not just markdown?

Serve `Accept: text/markdown` and an agent stops paying for your DOM. That is
one HTTP header, it works today, and nothing here argues against it —
[acceptmarkdown.com](https://acceptmarkdown.com) makes the case well. So the
honest version of the comparison starts by conceding the part markdown wins.

**It wins the token argument, very nearly outright.** The 16.3× below is
measured against live HTML. Against markdown it would almost vanish, because
markdown and the L0 projection carry the same text with different punctuation
around it. Bytes are not the differentiator and this project should not claim
they are.

What one header does not buy:

| | Stoa | Markdown |
|---|---|---|
| Vocabulary | Closed, 50 elements, mechanically checkable | Open-ended; CommonMark admits raw HTML, including `<script>` |
| Missing alternative text | Unrepresentable: `media.alt` is required and non-empty | `![](fig.png)` is valid markdown. The 0-of-65 finding below is not expressible as a check |
| Document identity | Structural digest over the tree, identical across JSON and CBOR | No canonical tree, so any digest is over bytes and a reserialisation breaks it |
| Excerpt proof | 224-byte Merkle proof for one paragraph, verifiable without the document | Requires a canonical tree. Not available |
| Unknown constructs | Declared fallback, in band, total | Extensions — tables, footnotes, admonitions, MDX — render as literal syntax in a reader that does not implement them |
| Exact quantities | Integer significand and scale; no float at any layer | No type system. *"0 amounts requiring a float"* is not a statement markdown can make |
| Interaction | L2: `field.label` is required, so an unlabelled control cannot be written | No interaction layer |
| Third-party fetch | Unrepresentable | Arbitrary image hosts and embedded HTML |
| Provenance | Register pinned by content hash, resolved offline | None |

Every row rests on the same thing: a closed vocabulary over a canonical tree.
Markdown is deliberately the opposite — an open surface for human prose in
which anything the parser does not recognise passes through as text. That is
the correct design for what markdown is for, and it is exactly what makes each
row above unavailable to it.

**So the relationship is not competition. Markdown is an input to this, not a
rival.** The reference surface is contained by CommonMark for the reason
acceptmarkdown gives — existing editors, diffs and review workflows should work
on day one — and `Accept: text/markdown` returns that surface (design notes
§11.3). Two things follow that a hand-maintained markdown copy cannot have: it
is generated from the tree being served, so it cannot drift from it; and it
satisfies a fixed-point test, so the markdown returned is markdown that
converts back to the same structural digest. Markdown extracted from a
rendering has neither property and cannot acquire them.

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
  for n = 1..118, CBOR edge cases and key-order determinism, injection, and
  degradation totality over synthetic instances of all 23 elements above L0.
- 5,000 generated hostile documents per fuzz run, 0 crashes. The first run
  found 272 in 3,000 — see `m0/FINDINGS.md` defect 12.
- **Archival provenance, offline.** A document may pin the vocabulary register
  it was written against by content hash (`document.register`).
  `stoa0.py <doc> provenance` resolves that pin against a local
  content-addressed archive and validates the document against *the register it
  claims*, not the one you happen to hold. Demonstrated on a real superseded
  register: `conformance/archived-01.json` is invalid against the current
  vocabulary and valid against the one it names. The pin is never resolved over
  a network — a hash is not a location, for the same reason renderers are named
  by hash.
- **Surface fixed point, both directions.** The conformance document written a
  second time in a CommonMark-contained surface syntax
  ([`conformance/conformance-01.stoa`](conformance/conformance-01.stoa), 63% of
  the canonical JSON): `tree → text → tree` preserves the structural digest
  exactly over all 50 elements, and `text → tree → text` is byte-identical.
  The tree direction is the one that matters — it proves the surface can
  express every element without losing a field, a child, or an order.

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

**The comparison is against HTML, not against markdown.** A markdown
projection captures most of the byte column for the cost of one HTTP header;
see [Why not just markdown?](#why-not-just-markdown). What it does not capture
is everything the byte column is not: a structure that is declared rather than
inferred, and an excerpt that verifies.

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
conformance/conformance-01.stoa  the same document in the surface syntax; generated
conformance/archived-01.json  a document pinned to a superseded register
spec/registers/               content-addressed archive of register versions
tools/                        throwaway M0 toolchain (Python, standard library only)
corpus/RESULTS.md             corpus 1: administrative notices (Diavgeia)
corpus/RESULTS-rfc.md         corpus 2: standards documents (IETF RFCs)
corpus/RESULTS-jats.md        corpus 3: scholarly articles (JATS)
corpus/RESULTS-forms.md       corpus 4: public-sector forms (tests L2)
corpus/RESULTS-law.md         corpus 5: UK legislation (CLML)
spec/EVIDENCE.md              what justifies each element; generated
design/design-notes.md        the working design document
corpus/sample/                one real notice as canonical JSON, HTML and text
m0/FINDINGS.md                what closing the vocabulary actually surfaced
docs/STATE.md                 where things stand, what is next, funding position
docs/GOVERNANCE.md            licensing, custody, amendment process, succession
docs/ROADMAP.md               milestones
docs/LICENSING.md             licence split and rationale
docs/NAME.md                  naming decision and how to undo it
```

### Five corpora, five genres, five markup languages

Every corpus is a live public source. None was assembled for this project, and
each genre was chosen for its importance to the format's purpose rather than for
the elements it happens to contain — that distinction is the whole point of the
evidence gate below.

| | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Genre | Admin notices | Standards | Scholarly articles | Public forms | Legislation |
| Source | [Diavgeia](https://diavgeia.gov.gr) | IETF RFCs | Europe PMC | GOV.UK, ECB, EP | [legislation.gov.uk](https://www.legislation.gov.uk) |
| Markup | JSON | RFC XML v3 | JATS | HTML | CLML |
| Tests | L0/L1 | L0/L1 | L0/L1 | **L2** | L0/L1 |
| Documents | 100 | 16 | 14 | 16 forms | 8 Acts |
| Produce a conforming document | 100% | 100% | 100% | 100% | 100% |
| Lose no source string | 100% | 100% | 100% | — | 100% |
| Need no element outside the register | 100% | 100% | 100% | 100% | 100% |

**138 documents. 100% on every component.** Reports:
[1](corpus/RESULTS.md) · [2](corpus/RESULTS-rfc.md) · [3](corpus/RESULTS-jats.md) ·
[4](corpus/RESULTS-forms.md) · [5](corpus/RESULTS-law.md)

Those numbers are the *end* state. Getting there is the interesting part, and
`m0/FINDINGS.md` records all seventeen defects the corpora found — four in the
format itself, the rest in the mappers.

### What corpus 2 falsified

`docs/STATE.md` §6 wrote down a prediction before any code existed:

> *"Do superscripts, layout tables, or inline icons turn out to be load-bearing
> in practice. **The register bets they are not.**"*

The RFC corpus produced 75 superscripts, and **every one was an exponent** —
`2^64`, `2^32`, `2^62`. With no superscript in the register they degraded to
`264` and `232`, inside sentences of the form *"an integer in the range
-2^64..2^64-1 inclusive"*. Not a formatting loss: **a wrong number in a
normative specification**, produced by a format whose entire numeric thesis is
exactness.

L0 gained `power` — semantic rather than presentational, because an exponent is
meaning and a superscript is appearance. The corpus went to 100%.

That episode is the argument for the method. A pre-registered prediction, a test
capable of refuting it, refutation with a number attached, and a fix that cost
nothing because the layer had not frozen. After the freeze the only remedy would
have been a new epoch.

### What corpus 3 measured: the accessibility claim

`media.alt` is a required, non-empty field, so a figure with no alternative text
is *unrepresentable*.

| | Count |
|---|---|
| Graphics in 14 real scholarly articles | 65 |
| Carrying alternative text in the source | **0 (0%)** |
| Carrying none | **65 (100%)** |

Every one would pass an HTML validator, ship, and fail a reader. Here none of
them is expressible: a conforming document did not exist until alternative text
was supplied.

Stated precisely, because the limit matters — the mapper had to *derive* that
text from figure captions, and derived text is worse than authored text. The
claim is not that the format writes good alt text. It is that **the absence is
impossible**, so the failure lands at build time in front of the author instead
of silently in front of a reader.

Corpus 4 is the same property applied to interaction: `field.label` is required,
so an unlabelled control cannot be written. Of 2,449 controls on well-run
public-sector sites, 2,446 carried a real `<label>` — a best case, and it still
contained two that this format cannot express.

### Is the register earned?

`spec/EVIDENCE.md`, generated by `mise run evidence`, classifies all 53
elements by what justifies them:

| Verdict | Count | Meaning |
|---|---|---|
| **CORPUS** | 34 | Exercised by **two or more independent genres**. Passes the gate. |
| **ONE GENRE** | 12 | Exercised by real documents, in one genre only. Not yet normative. |
| **PROVISIONAL** | 2 | L3. Declared provisional: implementable, removable, not normative. |
| **FIXTURE** | 2 | Exercised only by the conformance document. An assertion. |
| **UNTESTED** | 0 | — |

**L0 — the layer that freezes permanently — is 28 of 30 through the two-genre
gate, and 30 of 30 exercised by real documents.** That is the number that
governs the freeze. L1 and L2 are additive-only, so an unearned element there is
recoverable; at L0 it is not.

The gate is defined in `docs/GOVERNANCE.md` §4 and it runs in both directions.
It admitted `power` on evidence, and it removed `tab-group`, `tab` and
`epigraph` when five genres produced none — the register has shrunk twice and
grown once under it. That is the structural answer to the way constrained
formats die: they die through the escape hatch, the escape hatch opens one
reasonable-sounding element at a time, and **a persuasive argument cannot
satisfy a requirement to produce two unrelated bodies of real documents.**

## L0 is frozen

Taken deliberately on 27 August 2026, not reached by attrition. The full record
is [`docs/FREEZE.md`](docs/FREEZE.md); the short version:

```
L0 elements      30
frozen           2026-08-27
digest           269d4dce3149f8f2102d9d85d388bc13b162962cd21907e110f2c6e49f84f194
L0 FREEZE        intact
```

The digest covers the L0 element records and the definitions they rest on — the
field types and content models they name, the field spec, the global authoring
rules — and deliberately nothing else, so L1 and above stay additive without
disturbing it. `mise run check` fails if it moves. `tools/selftest.py` asserts
the check in both directions: eight mutations that must break it, six that must
not, because a freeze check that cried wolf would be argued away inside a year.

**Two of the 30 were frozen on one genre each,** and the record says so rather
than averaging it away: `media` (scholarly articles only) and `quantity`
(administrative notices only). The reasoning for admitting each, and the four
other risks accepted on the day, are §4 and §8 of the freeze record.

What is not frozen: L1 and L2 remain additive-only, L3 remains provisional, and
`contents` and `admonition` are still exercised only by the conformance
document — knowingly unearned, at the layer where that is survivable.

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
