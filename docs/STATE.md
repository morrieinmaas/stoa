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

**Versioning: freeze the floor, grow the ceiling.** L0 is closed permanently. L1 and above are additive only. Unknown elements are specified from 1.0 as "render the fallback." The version field is advisory and clients never negotiate on it. A genuine break becomes an epoch that coexists rather than a migration.

**The reverse bridge.** No forward bridge, ever. A publisher serves the canonical form and a prerendered static HTML projection from the same URL by content negotiation. Adoption is unilateral, there is no two-sided market to bootstrap, and the client is not the product.

**Content determinism, not pixel determinism.** Fonts are client-side, declared by role, never fetched. What is guaranteed identical is the render tree, not the rasterisation. The signature claim survives because HTML fails "what you see is what you sign" through *content* variance from scripts, not through font variance, and a format with no author code has content invariance regardless.

**The structural hash.** The digest is defined recursively over typed nodes, not over a serialisation, so the encoding is a revisable transport detail. Verified: canonical JSON and deterministic CBOR of the same document produce an identical digest and identical Merkle leaves. Merkle over block nodes gives excerpt proofs, so a single quoted paragraph is provable without transmitting the document.

**No floating point, anywhere.** Integers and scaled decimals only, including inside L3 payload data. Closes the encoding question and renderer numeric determinism across WASM hosts with one decision.

**The fetch boundary.** A document may name any resource the reader might choose to visit; it may not name any resource the client fetches without the reader acting. Fetched fields (`media.src`, `form.action`, `meta.theme`) cannot express a host at all. Three further client obligations: no speculative resolution of relation targets, no network lookup of unknown payload types, and language and grammar resources are local only. The generalisation: a document-controlled string that a client turns into a request is a covert channel whether or not it looks like a URL.

**Themes.** Tokens plus per-role rules, never a stylesheet language, never positional addressing. Publisher themes are one same-origin content-hash-pinned resource, optional to fetch, cached per publisher. Format defaults are themselves a normative theme and must pass the same conformance gate. Reader-installed themes are ungated because they are chosen; publisher themes are gated because they are imposed. A redesign is a republication, which is correct for anything signed or archived.

**Applications are a separate media type.** A document links to one and can never contain one. The escape hatch is what killed every constrained format before this. The triage rule, worked through on customer support in design notes 10.4: if the interaction needs the *page* to decide when to talk to the server, it is an application; if it needs the *reader* to decide, it is a document. HTMX is the closest thing in spirit to this design and differs on exactly that point, which makes it a good way to build the linked application and a bad thing to import into the format.

**Authoring surfaces are plural and non-normative.** The tree is the document; surfaces are input languages and there can be many. Removes the syntax argument and insulates the format from getting the first surface wrong. The reference surface should be contained by CommonMark so existing tooling works on day one.

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

**Blocking the L0 freeze:**

1. **Nothing mechanical — the freeze is now a judgement.** Five corpora across five genres are at 100% on every component. Every L0 element is exercised by real documents and 28 of 30 pass the two-genre evidence gate; the two that do not (`media`, `quantity`) each name the genre that would close them. L1 and L2 are additive-only, so an unearned element there is recoverable in a way an L0 one is not. Freezing L0 is now a decision to take deliberately rather than a task waiting on evidence. See `../spec/EVIDENCE.md`.

**Not blocking the freeze:**

2. Type identifier namespace. Who names `time-series`, and how are collisions handled.
3. Theme and renderer distribution. Content-addressed, but discovered how. Same question as 2.
4. Form submission response shape. Full tree or a patch. A patch reintroduces state reconciliation.
5. Multi-document site manifests. Does a manifest become where complexity accumulates.

**Honest weaknesses, recorded rather than solved:**

- **The stranded reader.** The properties most likely to make an individual care (portable themes, reader supremacy, a consistent environment) exist only for native-client users, while the adoption strategy correctly says nobody needs one. The bridging artifact is a browser extension applying reader themes to the HTML projection, and it should come before the terminal client.
- **The surface is untested.** Nobody has written a document in a surface syntax yet.

## 5. Immediate next actions, in order

1. ~~Run the corpus test.~~ Done, five times over. Seventeen defects found and fixed; see `../m0/FINDINGS.md`.
2. **Decide whether to freeze L0.** Nothing is blocking it mechanically. The open question is whether 30 of 30 exercised and 28 of 30 twice-exercised is enough, given that after the freeze the only remedy is a new epoch.
3. **Write the conformance document a second time in a surface syntax** and compare against the canonical version (M0c). It is a fixed-point test, not a taste test, and it is the last untouched milestone before M1.
4. **Do the governance chores**: register the trademark, mirror the repository, deposit with Software Heritage and Zenodo for a DOI. An afternoon, and the DOI is what makes it citable in a tender.
5. **Open one conversation with a public body about a paid pilot.** This is the single highest-value remaining action and no amount of further measurement substitutes for it.
6. **Start M1** (core types, encoding, parser, validator, HTML emitter, in Rust).
7. **Submit the NLnet application** when the general call reopens — see section 7 and `FUNDING.md` section 9.

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

### Position

**NLnet is the right funder and the timing is unusually good.** NLnet has funded protocol and standards work for individuals for a decade, explicitly at the pre-adoption R&D stage, which is exactly the stage this is at. Grants run €5,000 to €50,000 for a first proposal, up to €150,000 subsequently, with a €500,000 lifetime cap. Projects are one to twelve months, the main application is about two pages, and individuals are eligible, so no company structure is required to apply.

**The window.** The NGI Zero Commons Fund closed its thirteenth and final call on 1 June 2026. NLnet paused general submissions to take stock and prepare the transition to the Open Internet Stack, prompted by the Commission's Tech Sovereignty package of 3 June 2026. Regular calls reopen after the European summer, alongside three new programmes under the Open Internet Stack umbrella, and NLnet has been selected to run a €10M Open Internet Stack cascade funding call plus two pilots. Practically: applications reopen around September 2026, which is roughly the time it takes to finish the corpus test and M1.

**Strategic fit.** The EU Open Source Strategy names support for new open source building blocks in critical technology areas including future internet architectures, and long-term stewardship through an Open Source Maintenance Instrument. A document format built for European public sector accessibility, verifiable public records, and archival integrity is close to a poster child for that narrative. Write the application in that vocabulary: sovereignty, interoperability, digital commons, reusable public digital assets.

### What makes this application unusual

Most two-page applications describe intended work. This one can attach work already done: a closed vocabulary register, a conformance document exercising all 50 elements, a ruleset catching 13 deliberate faults, a degradation contract verified over 121 content units, encoding independence demonstrated across two serialisations, and a written governance document answering the stewardship question. Very few proposals can answer stewardship at all.

### Scoping the ask

Scope to what is completable in six to twelve months, not to the vision:

- Reference compiler in Rust (core types, canonical encoding, parser, validator).
- Conformance suite and test corpus.
- Accessibility attestation toolchain and CI action.
- Corpus validation against a real public register.

Not "the format." Not "a new internet."

### Honest reading of the money

NLnet pays cost-recovery, not commercial rates, so €50,000 over six to twelve months is a fraction of a consulting day rate. That is fine and it is the correct use of it: the grant funds the parts no client will ever pay for, meaning the specification and the conformance suite, while paid pilot work with a public body funds the rest.

The larger asset is not the money. It is **legitimacy transfer**. Being an Open Internet Stack grantee is a citable credential in the room where a public body decides whether to depend on a format written by one person, which is the same question the governance document answers. It also compounds: the first grant is a rung toward €150,000 follow-ons against the lifetime cap, not a payout.

### Other routes

- **A paid pilot with one public body** is better money and much better validation than any grant, and it supplies the thing a grant cannot: evidence somebody wanted it.
- **Horizon Europe Cluster 4 Open Internet Stack** calls are consortium-scale rather than solo, but joining an existing consortium is plausible later.
- **Greek and regional programmes** (ESPA cycles, Region of Crete) suit the applied pilot rather than the format itself.
- **Archival and accessibility bodies** (national libraries, digital preservation organisations) are small money but strong legitimacy, and the archival claim is genuinely aimed at them.

### One thing to check separately

How grant income to an individual interacts with the Greek relocation and IKE timing. It differs depending on whether the application is personal or through a company, and it is worth knowing before applying rather than after.

## 8. Risks, ranked

1. **The corpus test fails.** Real documents need elements outside the register. Cheap to fix now, impossible after the freeze. Mitigation: run it first.
2. **Nobody publishes.** Mitigated structurally by the reverse bridge, which makes adoption unilateral, but the first real corpus still has to come from somewhere.
3. **Governance never becomes real.** The interim document buys time, not permanence. A public body will eventually need an institution.
4. **Scope creep into applications.** Every constrained format has died by its escape hatch. The rule is written down precisely because it will be tested.
5. **Solo maintainer burnout.** The format is designed to outlive its author; the project currently is not.
