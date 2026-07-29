# Stoa

> **Superseded.** The project README now lives at the repository root and
> carries the measured M0 and corpus numbers. This file is kept as the
> original framing note. Design prose in this directory (`STATE.md`,
> `GOVERNANCE.md`, `ROADMAP.md`, `NAME.md`, `LICENSING.md`) remains current.

A hypermedia document format and conformance profile, transported over unmodified HTTPS.

Not a protocol, not a browser, not an alternative internet. The closest structural analogue is PDF/A: a constrained format defined by what it guarantees rather than by what it can express.

**Status:** design notes and an M0 vocabulary experiment. Not a specification, not an implementation. Nothing here is stable.

---

## What this is

A document format with a finite semantic vocabulary (53 elements), delivered over ordinary HTTPS, where the document carries meaning and structure and never carries appearance. Presentation is supplied by themes written against the vocabulary rather than against any individual site, and reader preferences override publisher styling with no mechanism for the publisher to override back.

The client fetches content and nothing else: no scripts, no stylesheets per document, no font files, no third-party subresources. A document cannot name a host that the client will contact without the reader acting, so third-party requests are unrepresentable rather than forbidden.

Four conformance layers. Every layer degrades in band to the one below, so a client implementing only L0 obtains the complete meaning of any conforming document, including documents published years after that client shipped. That single property does double duty as the accessibility guarantee and as the forward-compatibility mechanism.

## What this is not

Not a replacement for the web. Not an application platform. Not a way to render existing web pages. Applications are a separate resource type that a document may link to and can never contain.

## Why

Four claims that are hard to make anywhere else, all of them mechanically checkable rather than asserted:

- **Accessibility by construction.** Structural failures are unrepresentable, and the mechanically detectable content failures are build errors. A sampled recurring audit becomes a complete build-time check.
- **Verifiable content.** The document digest is defined over the tree rather than over any serialisation, so it is signable, and a Merkle construction over block nodes makes individual paragraphs independently provable without transmitting the document.
- **Bounded, declared rendering cost.** A line a procurement officer can put in a tender.
- **Meaning is emitted, not recovered.** A consumer that wants structure without presentation — screen reader, terminal client, archival indexer, autonomous agent — reads the normative L0 projection rather than inferring structure from a rendering. Measured against the live corpus: 1,361 bytes against 22,187, of which 89% of the live payload is markup a machine reader pays for and cannot use. Same mechanism as the accessibility claim, measured from the other end.

## Layout

```
design/design-notes.md      the working design document (read this first)
spec/vocabulary.json        the vocabulary register, normative, machine-readable
spec/EVIDENCE.md            what justifies each element; generated
spec/VOCABULARY.md          generated from it; do not edit by hand
conformance/                the conformance document, negative fixture, golden output
tools/                      throwaway M0 toolchain (Python, stdlib only)
corpus/RESULTS.md           corpus 1: administrative notices (Diavgeia)
corpus/RESULTS-rfc.md       corpus 2: standards documents (IETF RFCs)
m0/FINDINGS.md              what closing the vocabulary actually surfaced
docs/GOVERNANCE.md          licensing, custody, amendment process, succession
docs/STATE.md               where things stand, what is next, funding
docs/ROADMAP.md             milestones
docs/FUNDING.md             the funding application
docs/NAME.md                naming decision and how to undo it
```

`design/design-notes.md` is now written, with stable section numbering, so the
cross-references from `GOVERNANCE.md` and `STATE.md` resolve.

## Running the M0 toolchain

Python 3, standard library only, no dependencies.

```sh
python3 tools/stoa0.py conformance/conformance-01.json all     # canonicalise, validate, contract, merkle
python3 tools/stoa0.py conformance/negative-01.json check      # must report 13 errors
python3 tools/stoa0.py conformance/conformance-01.json l0      # the L0 text projection
python3 tools/structhash.py conformance/conformance-01.json    # encoding independence
```

Or with `mise`:

```sh
mise run check      # everything, and fails loudly if it should not
```

Current expected output:

```
distinct types   53 of 53 in register
check            0 errors, 0 warnings
contract         98 units checked, 0 lost in projection to L0
merkle blocks    124   proof size 7 sibling hashes (224 bytes)   verifies True
ENCODING INDEPENDENT True
```

## The one thing standing between here and freezing L0

A third genre containing footnotes and figures. Two corpora are at 100%, and the
second one falsified the superscript bet and was fixed. What remains is that
three L0 elements (`media`, `note`, `note-ref`) are exercised by no real
document yet. See `../spec/EVIDENCE.md`.

## Licensing

Split three ways, all irrevocable, all permitting independent implementation without permission. See `LICENSING.md` and `GOVERNANCE.md`.
