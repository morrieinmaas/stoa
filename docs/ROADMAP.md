# Roadmap

Milestones from `design/design-notes.md` section 13, with current status.

| | Milestone | Status |
|---|---|---|
| **M0** | Vocabulary register and conformance document, hand-written in canonical form, before any code. Simultaneously the test fixture, the theme validation target, and the thing that forces the vocabulary to close. | **Done.** 53 elements, 4 defects found and fixed. |
| **M0b** | Corpus coverage test against a real public register. The last thing gating the L0 freeze. | **Done.** 100 acts from Diavgeia, 10 act types, 66 bodies: 100% coverage, 0 missing elements, 0 amounts needing a float. Did not falsify the vocabulary. See `../corpus/RESULTS.md`. |
| **M0b2** | A second corpus in a second genre, to exercise what the administrative corpus never touched. | **Done.** 16 IETF RFCs in XML v3: 100% produce conforming documents, 30 of 53 elements exercised, and it **falsified the superscript bet** — 75 exponents that degrade to corrupted numbers. See `../corpus/RESULTS-rfc.md`. |
| **M0b3** | Decide how to represent an exponent and add it. | **Done.** L0 gained `power`; the RFC corpus went to 100%. |
| **M0b4** | A third corpus in a genre with figures and footnotes, to settle the three L0 elements no other genre reached. | **Done.** 14 JATS articles: 100% on every component, `media`/`note`/`note-ref` all earned, and 0 of 65 real figures carried alternative text. |
| **M0d** | Freeze L0. Now a deliberate judgement rather than a task waiting on evidence: every L0 element is corpus-backed, four L1 elements are not. | **Next.** `../spec/EVIDENCE.md`. |
| **M0c** | Write the conformance document a second time in a surface syntax; compare as a fixed-point test. | Not started. |
| **M1** | Core types, canonical encoding, NFC, structural hash. Parser for L0 and L1. Validator. HTML emitter. Ends with real publishable documents and a 6 KB page to show someone. | Not started. |
| **M2** | Theme engine, base role set, three reference themes, theme conformance checker. Browser extension applying reader themes to the HTML projection. Client conformance tests for the unprompted-action rules. | Not started. |
| **M2b** | Terminal client, as a conformance proof that non-visual targets are siblings rather than accommodations. | Not started. |
| **M3** | Attestations and a CI action. The point at which it becomes sellable to a public body, and earlier than most people would guess. | Not started. |
| **M4** | L2 interaction, addressable state, form submission. | Not started. |
| **M5** | WASM host, anchored text resolution, one reference renderer (time series), build-time execution path. | Not started. |
| **M6** | Paginated and archival projections with embedded fonts. No longer a research problem, so it can move earlier if an adopter asks. | Not started. |

## Test suite invariants (M1 onward)

1. **Encoding independence.** Encode the same tree two ways, assert one structural digest.
2. **Degradation contract as a property test.** For any generated document, project to L0 and assert every text node survives.
3. **Golden outputs.** Snapshot every projection of the conformance document.
4. **Surface fixed point.** `text -> tree -> text` returns the original text.

Plus fuzzing on the parser, because it will eventually eat untrusted input.
**Running since M0** (`tools/fuzz.py`): 5,000 generated hostile documents per
run, deterministic by seed. The first run found 272 crashes in 3,000 cases, all
in code that trusted its own input. See `../m0/FINDINGS.md` defect 12.

## Non-code track

- Trademark filing (EUIPO classes 9 and 42).
- Licence files in place; repository mirrored on two independent providers.
- Software Heritage deposit; Zenodo release with a DOI.
- NLnet application when calls reopen after summer 2026.
