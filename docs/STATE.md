# State of play

Written 28 July 2026. Where the project stands, what is settled, what is not, what to do next, and the funding position.

---

## 1. The idea, in one paragraph

An alternative document layer for the internet: a finite, closed semantic vocabulary delivered over ordinary HTTPS, where a document carries meaning and never carries appearance, presentation comes from themes written against the vocabulary rather than against any site, and the reader outranks the publisher. Not an application platform, and no mechanism for one to leak in. The bet is that most of what public bodies, gazettes, registers, and reference sites publish needs a small fixed set of elements, and that constraining to that set buys properties that are impossible on the open web: accessibility by construction, cryptographically verifiable content, and a rendering cost that can be declared in advance.

A fourth property falls out of the same decision and has become more valuable than it looked when the design started. Because meaning is carried and appearance is not, every consumer that wants structure without presentation reads the same normative L0 projection: screen readers, terminal clients, archival indexers, and — increasingly the dominant reader — autonomous agents. Those are one audience, not four. A machine reader on the open web ingests a rendering and infers structure from it; measured against the first corpus, 89 percent of what it ingests is markup it cannot use, and every inference it makes is a guess the publisher never confirmed. Here the structure is declared, so there is no inference step, and because block nodes are Merkle-provable a cited paragraph is verifiable rather than merely quoted. This is the accessibility guarantee restated for a different consumer, which is the argument for why it is a property of the design rather than a feature bolted onto it.

## 1a. What category this is

A hypermedia document format plus a conformance profile, transported over unmodified HTTPS. Registration path is an IETF media type under RFC 6838, not an IETF protocol. Architecturally a narrow waist: one canonical tree, plurality of input surfaces above it, plurality of clients and renderers below.

For the NLnet application the category to tick is **open standards**, with software as the attached deliverable. That matches the EU Open Source Strategy language on interoperability and reusable public digital assets better than "software project" does.

Framings by audience:

| Audience | Framing |
|---|---|
| Standards and technical | A hypermedia document format and conformance profile, transported over HTTP. |
| Funding and EU policy | An open standard for machine-verifiable, accessible-by-construction public documents. |
| Procurement | A publishing format with certifiable accessibility, integrity, and cost properties. |
| Machine and agent consumption | A publishing format whose structure is declared rather than inferred, and whose excerpts are independently verifiable. |

Never: alternative internet, new browser, new protocol.

## 2. What is settled

Decisions that survived scrutiny and are unlikely to move.

**The four layers, and the degradation contract.** L0 content (frozen), L1 structure, L2 interaction, L3 typed rendering. Every element above L0 projects into the layer below, in band, so a client implementing only L0 gets complete meaning. This one rule does double duty: it is the accessibility guarantee and it is the versioning mechanism, because a client that has never heard of an element added years later still renders it correctly via its fallback.

**L0 is frozen.** Taken deliberately on 27 August 2026: 30 elements, digest `269d4dce3149f8f2102d9d85d388bc13b162962cd21907e110f2c6e49f84f194`, pinned in the register and asserted by `mise run check`. The digest covers the L0 records plus the definitions they rest on and nothing else, so L1 and above stay additive without disturbing it, and `tools/selftest.py` asserts the check bites in both directions. Two of the 30 (`media`, `quantity`) were frozen on one genre each and the record says so rather than averaging it away. `FREEZE.md`.

**Versioning: freeze the floor, grow the ceiling.** L0 is closed permanently. L1 and above are additive only. Unknown elements are specified from 1.0 as "render the fallback." The version field is advisory and clients never negotiate on it. A genuine break becomes an epoch that coexists rather than a migration.

**The reverse bridge.** No forward bridge, ever. A publisher serves the canonical form and a prerendered static HTML projection from the same URL by content negotiation, and the same negotiation serves `text/markdown` (the CommonMark-contained surface) and `text/plain` (the L0 projection). Every representation is generated from the tree, so none can drift from another. Adoption is unilateral, there is no two-sided market to bootstrap, and the client is not the product.

**Content determinism, not pixel determinism.** Fonts are client-side, declared by role, never fetched. What is guaranteed identical is the render tree, not the rasterisation. The signature claim survives because HTML fails "what you see is what you sign" through *content* variance from scripts, not through font variance, and a format with no author code has content invariance regardless.

**The structural hash.** The digest is defined recursively over typed nodes, not over a serialisation, so the encoding is a revisable transport detail. Verified: canonical JSON and deterministic CBOR of the same document produce an identical digest and identical Merkle leaves. Merkle over block nodes gives excerpt proofs, so a single quoted paragraph is provable without transmitting the document.

**No floating point, anywhere.** Integers and scaled decimals only, including inside L3 payload data. Closes the encoding question and renderer numeric determinism across WASM hosts with one decision.

**The fetch boundary.** A document may name any resource the reader might choose to visit; it may not name any resource the client fetches without the reader acting. Fetched fields (`media.src`, `form.action`, `meta.theme`) cannot express a host at all. Three further client obligations: no speculative resolution of relation targets, no network lookup of unknown payload types, and language and grammar resources are local only. The generalisation: a document-controlled string that a client turns into a request is a covert channel whether or not it looks like a URL.

**Themes.** Tokens plus per-role rules, never a stylesheet language, never positional addressing. Publisher themes are one same-origin content-hash-pinned resource, optional to fetch, cached per publisher. Format defaults are themselves a normative theme and must pass the same conformance gate. Reader-installed themes are ungated because they are chosen; publisher themes are gated because they are imposed. A redesign is a republication, which is correct for anything signed or archived.

**Applications are a separate media type.** A document links to one and can never contain one. The escape hatch is what killed every constrained format before this. The triage rule, worked through on customer support in design notes 10.4: if the interaction needs the *page* to decide when to talk to the server, it is an application; if it needs the *reader* to decide, it is a document. HTMX is the closest thing in spirit to this design and differs on exactly that point, which makes it a good way to build the linked application and a bad thing to import into the format.

**Authoring surfaces are plural and non-normative.** The tree is the document; surfaces are input languages and there can be many. Removes the syntax argument and insulates the format from getting the first surface wrong. The reference surface is contained by CommonMark so existing tooling works on day one, with two generic extensions (`::: block` and `{{inline}}`) for what CommonMark has no construct for. Verified rather than asserted: `tree -> text -> tree` preserves the structural digest over all 50 elements, and `text -> tree -> text` is byte-identical.

## 3. What is built

M0, M0b and M0b2 are complete and run. All figures below are produced by `mise run check` and `mise run corpora`. See `../m0/FINDINGS.md`.

- Vocabulary register: 50 elements (L0 30, L1 10, L2 8, L3 2 plus 5 render primitives).
- Conformance document exercising all 52, in canonical form, 9,359 canonical bytes.
- Negative fixture with 13 deliberate faults across 13 distinct rules; the ruleset reports exactly 13 errors.
- Degradation contract verified mechanically: 91 content units, 0 lost projecting to L0, and the projection is itself conforming.
- Encoding independence verified across canonical JSON and deterministic CBOR: identical digest, identical Merkle leaves.
- Merkle excerpt proofs: 118 blocks, 224-byte proof, verifies at every index, and fails on a tampered block at every index.
- Five corpora over 138 documents in five markup languages, all at 100% on conformance, no-loss and no-omission: 100 Diavgeia acts; 16 IETF RFCs (which falsified the superscript bet and drove `power` into L0); 14 JATS articles (which settled `media`, `note`, `note-ref`, and measured 0 of 65 real figures carrying alternative text); 16 public-sector forms (which is what tests L2); and 8 UK Acts in CLML.
- Evidence audit (`../spec/EVIDENCE.md`, generated): 34 of 50 elements pass the two-genre gate, 12 exercised in one genre, 2 provisional (L3), 2 fixture-only, 0 untested. **L0 is 28 of 30 through the gate and 30 of 30 exercised by real documents.**
- Accessibility measured, not asserted: 0 of 65 real figures carried alternative text, and none of them is expressible without it.
- 19 toolchain self-tests and 5,000 hostile documents per fuzz run, 0 crashes.

M0 found four defects that were free to fix then and would have been impossible after the freeze. The most important: `media.src` was an absolute IRI, which meant the layer about to freeze permanently permitted tracking pixels with good alt text. It was found by writing out a media example, not by reasoning about the design. That is the argument for building the fixture before writing normative text, and it is the single most valuable thing produced so far.

## 4. What is open

**Settled since this section was written:** the L0 freeze, taken 27 August 2026. The two elements that did not clear the two-genre gate (`media`, `quantity`) were frozen anyway, on reasoning recorded in `FREEZE.md` §4, together with the four other risks accepted on the day.

**Open:**

2. Type identifier namespace. Who names `time-series`, and how are collisions handled.
3. Theme and renderer distribution. Content-addressed, but discovered how. Same question as 2.
4. Form submission response shape. Full tree or a patch. A patch reintroduces state reconciliation.
5. Multi-document site manifests. Does a manifest become where complexity accumulates.

**Honest weaknesses, recorded rather than solved:**

- **The stranded reader.** The properties most likely to make an individual care (portable themes, reader supremacy, a consistent environment) exist only for native-client users, while the adoption strategy correctly says nobody needs one. The bridging artifact is a browser extension applying reader themes to the HTML projection, and it should come before the terminal client.
- **The surface is untested.** Nobody has written a document in a surface syntax yet.

## 5. Immediate next actions, in order

1. ~~Run the corpus test.~~ Done, five times over. Seventeen defects found and fixed; see `../m0/FINDINGS.md`.
2. ~~**Decide whether to freeze L0.**~~ Done, 27 August 2026. 30 of 30 exercised and 28 of 30 twice-exercised was judged enough; `FREEZE.md` records the two that were not and why they were frozen regardless.
3. ~~**Write the conformance document a second time in a surface syntax.**~~ Done (M0c). Both fixed points hold over all 50 elements; the surface document is `../conformance/conformance-01.stoa`.
4. **Do the governance chores**: register the trademark, mirror the repository, deposit with Software Heritage and Zenodo for a DOI. An afternoon, and the DOI is what makes it citable in a tender.
5. **Open one conversation with a public body about a paid pilot.** This is the single highest-value remaining action and no amount of further measurement substitutes for it.
6. **Serve the reverse bridge.** One URL, real `Accept` negotiation across the canonical tree, `text/html`, `text/markdown` (the surface) and `text/plain` (the L0 projection) — design notes §11.3. Every representation already exists as an emitter; what does not exist is a URL, and after five corpora there is still nothing anyone can look at. It also turns §11.3's two claims into assertions: that no representation can drift, and that the markdown served converts back to the same structural digest.
7. **Start M1** (core types, encoding, parser, validator, HTML emitter, in Rust).
8. **Submit the NLnet application** when the general call reopens — see section 7 and `FUNDING.md` section 9.

## 6. The corpus test (original plan, retained for the record)

> **Superseded by events.** This was written as a plan. It ran, five times, across five genres. The bet recorded in point 2 below — that superscripts are not load-bearing — was falsified: see `../m0/FINDINGS.md` defect 8. Results are in `../corpus/`.

The fastest remaining way to falsify L0, and it is a two-day throwaway.

Take 100 real Diavgeia or KIMDIS notices. Define the L0 subset as a JSON tree shape. Write a roughly 300-line Python emitter as a fold over the tree, one function per element, producing HTML plus a text projection. Then measure four things:

1. **Coverage.** What fraction of real notices are expressible with no element outside the register. Below roughly 95 percent means the vocabulary is wrong, not that the corpus is unusual.
2. **The omissions.** Do superscripts, layout tables, or inline icons turn out to be load-bearing in practice. The register bets they are not.
3. **Numerics.** Does anything genuinely need a float now that they are unrepresentable. Currency should never have been one; coordinates and measurements are the risk.
4. **Envelope figures.** The four classes carry placeholder numbers. Real documents set them.

Also worth measuring for its own sake: emitted bytes, request count, and time to first content against the live site. If those numbers are not startling, the pitch is wrong, and two days is a cheap way to find out.

A high coverage number is also the single most persuasive line available for a funding application, which is why this runs before the application rather than after.

## 7. Funding

Position, targets and the application itself are kept out of this repository:
they reference client engagements and the maintainer's business details,
neither of which belongs in a public standards repository.

What is public and relevant here: the work is licensed so that anyone may
implement it without permission (`LICENSING.md`), governance and succession are
answered in advance (`GOVERNANCE.md`), and every figure quoted anywhere about
this project is reproduced by `mise run check` and `mise run corpora`.

## 8. Risks, ranked

1. **The corpus test fails.** Real documents need elements outside the register. Cheap to fix now, impossible after the freeze. Mitigation: run it first.
2. **Nobody publishes.** Mitigated structurally by the reverse bridge, which makes adoption unilateral, but the first real corpus still has to come from somewhere.
3. **Governance never becomes real.** The interim document buys time, not permanence. A public body will eventually need an institution.
4. **Scope creep into applications.** Every constrained format has died by its escape hatch. The rule is written down precisely because it will be tested.
5. **Solo maintainer burnout.** The format is designed to outlive its author; the project currently is not.
