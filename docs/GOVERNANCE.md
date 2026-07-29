# Governance

**Status:** interim. This is the answer to "what happens if you stop," written before it is needed rather than after.

A format that public bodies build statutory obligations on cannot be one person's project. That is a procurement blocker rather than a nicety, and it arrives with the first serious adopter, not after them. Forming an institution now would be premature and would ossify a design that is not yet right. This document is the cheap version that answers the question honestly in the meantime.

---

## 1. Licensing

Three artifact classes, three licences, chosen so that nothing here can ever require permission to implement.

| Artifact | Licence | Why |
|---|---|---|
| Specification text, register, design notes | CC BY 4.0 | Permits independent implementation, derivative specifications, and translation, in perpetuity, irrevocably. Attribution is the only condition. |
| Conformance document, negative fixtures, golden outputs, reference themes | CC0 1.0 | Test data must have zero friction. A conformance suite that carries obligations is a conformance suite people route around. |
| Reference implementation and tooling | Apache-2.0 | OSI-approved, and unlike MIT it carries an explicit patent grant. For a format, that grant is the point. |

**Patent position, stated explicitly in the specification text:** no patent claims are asserted over the format, the canonical encoding, the structural hash, or any conformant implementation, and none will be. Implementation is royalty-free and unconditional. This sentence exists because a procurement lawyer will look for it, and its absence reads as an unanswered question.

**Irrevocability.** CC BY 4.0 and Apache-2.0 are both irrevocable for the versions published under them. That is the property being bought. A licence that can be withdrawn is not an answer to the succession question, it is a restatement of it.

## 2. Trademark, the one reserved right

The name is held as a trademark (EUIPO, classes 9 and 42) and is the only right not granted freely.

This is the standard model and the reason for it is conformance rather than control: anyone may fork the format, implement it, extend it, or compete with it, but only conforming implementations may use the name. Without that, "this document is [name]-conformant" means nothing, and the accessibility and integrity claims that rest on conformance become unenforceable.

Trademark policy, in one line: use of the name for a conforming implementation, or to refer to the format, needs no permission. Use of it for something non-conforming does.

## 3. Custody of the normative artifacts

**Normative set:** the specification text, the vocabulary register, the conformance document and fixtures, the theme conformance suite, the reference themes, and the format defaults.

**Custody arrangements, all of which exist today rather than on adoption:**

- A canonical repository, plus at least two independent mirrors on different providers in different jurisdictions.
- Every release is content-addressed. Release artifacts are published with their hashes, and tags are signed.
- The specification is deposited with an archive that is not operated by the author (Software Heritage for the repository, Zenodo for versioned releases with a DOI). A DOI is what makes it citable in a tender document and findable after any given hosting arrangement ends.
- No normative artifact is hosted only on a platform that could remove it.

## 4. Amendment process

"Additive only" (design notes 9.2) is a promise until it is a procedure. The procedure:

**L0 is frozen and this process cannot alter it.** No amendment, at any point, in any epoch. If L0 is wrong, the answer is a new epoch (9.5) coexisting with this one, never a change to this one. This paragraph is the load-bearing sentence in the document.

For everything else:

1. **Proposal.** A written case containing: the need, at least three real documents that cannot be expressed without it, the proposed element or field, and its normative degradation into the layer below.
2. **Degradation test.** The proposal is rejected outright if the element cannot degrade without losing meaning. This is mechanical, not a matter of opinion (design notes 3.6).
3. **Base role.** If the proposal introduces a semantic role, it must declare the existing base role it inherits from, so that themes written before it still render it (4.5).
4. **Public comment.** A fixed minimum period, in the open, with comments retained.
5. **Corpus evidence.** *(Added after M0b: this is the load-bearing gate.)* The element does not become normative until **at least two independent corpora, in different document genres, exercise it** — corpora nobody assembled for the purpose of justifying this element. "Three real documents that cannot be expressed without it" (step 1) is the proposer's claim; this is the check on it, and it is mechanical: `tools/evidence.py` classifies every element in the register as CORPUS, FIXTURE or UNTESTED and is run in CI.

   This is the answer to the question that kills constrained formats. Every one of them died through its escape hatch, and the escape hatch is always opened one reasonable-sounding element at a time. Discipline does not survive a decade; a gate that says *show me two unrelated bodies of real documents that needed this* does, because it cannot be satisfied by a persuasive argument.

   It is also symmetrical: the gate has already been used to **remove** elements. `tab-group` and `tab` were cut when four corpora failed to produce a single instance — and cutting them cost nothing, because they degraded to sections, which is what a publisher should have used.

6. **Provisional acceptance.** An element that passes the design tests but has no corpus evidence ships marked `"status": "provisional"` in the register. Provisional elements are implementable and testable, are **not** normative, and carry no permanence guarantee. They are removable. L3 (`payload`, `rendering`) is provisional today for exactly this reason: no corpus of published documents can produce a typed renderer payload, so the evidence gate cannot be satisfied by observation and must wait on two independent implementations instead.

7. **Normative.** Once normative it is permanent. There is no removal, only deprecation as a documentation state.

Deliberately slow, and deliberately **two-way**. A format whose vocabulary is easy to extend does not have a finite vocabulary, and the finiteness is the product. The addition path is gated by evidence from unrelated corpora; the removal path stays open for anything not yet normative. An element that no real document has ever needed is a liability, not an asset, and the register is expected to shrink at least as often as it grows before L0 freezes.

## 5. Succession

**Trigger conditions**, any of which starts the transfer: the maintainer states an intention to step down; the maintainer is unreachable for a stated period; the maintainer is unable to continue.

**On trigger:**

- Custody of the normative artifacts transfers to a named successor or successor organisation, recorded in the repository and reviewed annually.
- The trademark transfers with custody, subject to the same policy.
- If no successor is available, the trademark is released and the name enters the public domain. That outcome is worse than an orderly transfer and better than an abandoned name nobody may lawfully use.

**Intended eventual custodians**, roughly in ascending order of cost and legitimacy:

- A foundation formed around the format, once adoption justifies the overhead.
- An existing digital-public-goods steward with a record of holding specifications rather than shipping products.
- A national or European public body with an archival or accessibility remit. The strongest legitimacy and the slowest clock.

**What is explicitly not intended:** a standards committee formed before the design is right. The sequence that works is that one author decides, publishes, and gets it used, and custody transfers once there is something worth having custody of. Committee-first is how good formats become slow bad formats.

## 6. What this document does not claim

It does not claim an institution exists. It claims that the licences are irrevocable, the artifacts are archived outside the author's control, the amendment process is written down, and there is a stated answer to the succession question. That is enough to answer a procurement officer honestly, and it is enough to justify a public body depending on the format before there is a foundation behind it.

Review annually. Replace with real governance the moment there is enough adoption to warrant it.
