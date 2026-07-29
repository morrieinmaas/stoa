# Design notes

The working design document. Written after M0 rather than before it, which is
the wrong order for a specification and the right order for a design: the
vocabulary was closed first, the conformance document was written by hand
against it, and the four defects that surfaced (`../m0/FINDINGS.md`) changed the
design before any of it was written down as normative text.

**Status.** Design rationale, not normative text. The normative artifacts are
`../spec/vocabulary.json` (the register) and the conformance fixtures. Where
this document and the register disagree, the register wins and this document is
the bug. Section numbering is stable: `GOVERNANCE.md`, `STATE.md` and
`ROADMAP.md` cite it.

---

## 1. What this is

A hypermedia document format and conformance profile, transported over
unmodified HTTPS. Registration path is an IETF media type under RFC 6838, not
an IETF protocol.

The design is a narrow waist. One canonical tree in the middle; a plurality of
authoring surfaces above it; a plurality of clients, themes and renderers below.
Everything that is allowed to vary is pushed to one side or the other of that
waist, and the waist itself is small enough to freeze.

The bet: most of what public bodies, gazettes, registers and reference sites
publish needs a small fixed set of elements, and constraining to that set buys
properties that are unobtainable on the open web. Those properties are the
product. The format is the mechanism.

## 2. The layer model

Four layers. Each is a superset of the one below in expressive power, and each
is required to degrade into the one below without losing meaning.

| Layer | Carries | Frozen |
|---|---|---|
| **L0** | Content: the text, its structure, and the relationships between parts | Permanently, on release |
| **L1** | Structure: document-scale organisation that could be expressed at L0 more verbosely | Additive only |
| **L2** | Interaction: reader-initiated state changes and submission | Additive only |
| **L3** | Typed rendering: data that a declared renderer turns into a display list | Additive only |

A client that implements only L0 obtains the complete meaning of any conforming
document, including documents that use elements added years after that client
shipped. That is the whole design in one sentence, and §3 is how it is enforced.

## 3. The degradation contract

### 3.1 The rule

Every element above L0 declares, in the register, the element it degrades into.
The declaration is normative. Projection to L0 is a total function from a
conforming tree to a conforming tree.

### 3.2 Why in band rather than out of band

The alternative designs are a fallback attribute (like `alt`), a separate
fallback document, or content negotiation. All three let the fallback drift from
the content, because nothing forces them to be updated together. Degradation
here is computed *from* the element rather than supplied alongside it, so it
cannot drift. There is no second copy to forget.

### 3.3 The contract does double duty

The same rule is the accessibility guarantee and the versioning mechanism.
An element the client has never heard of and an element the client has chosen
not to implement are the same case, handled by the same code path. Formats that
treat forwards-compatibility and accessibility as separate problems end up with
two mechanisms, each with its own failure mode.

### 3.4 What "without losing meaning" means

Meaning is operationalised as *content units*: anything that produces
reader-visible characters. A text node is a unit; so is a quantity, a date, and
a string carried in a field that renders as text, such as `media.alt` or
`disclosure.summary`. The contract is that the multiset of content units in the
projection is a superset of the multiset in the source.

This is deliberately a low bar on presentation and a high bar on content. A
degraded `admonition` loses its colour and keeps its words. That is the correct
direction: salience degrades to language, never to nothing.

### 3.5 The projection must itself conform

Projecting a conforming document must produce a conforming document. This sounds
too obvious to state, and M0 found two violations of it (`../m0/FINDINGS.md`
defects 2 and 3), so it is stated.

It has a consequence that is not obvious: **the degradation graph and the content
models are not independent.** If element `X` degrades to `Y`, then no element
that permits `X` as a child may forbid `Y` as a child. `figure` admitting a
`rendering` child broke exactly this, because a figure containing a rendering
degraded into a figure containing a figure.

### 3.6 The degradation test, and why it is mechanical

**A proposed element that cannot degrade without losing meaning is rejected.
This is a mechanical test, not a matter of opinion.**

The test is: construct a minimal instance of the proposed element, project it,
and compare content units before and after. If any unit is lost, the proposal
fails. If the projection does not validate, the proposal fails. Neither
question requires a judgement about whether the element is a good idea.

This is what keeps the amendment process (`../docs/GOVERNANCE.md` §4) from
becoming a taste committee. Most bad proposals fail here, in public, on a
reproducible test, and the discussion never has to become an argument about
whether the proposer's use case is legitimate.

The test runs today, over every element above L0 rather than only those the
conformance document happens to use: `python3 tools/selftest.py`.

## 4. Themes and roles

### 4.1 Themes are not a stylesheet language

A theme is tokens plus per-role rules. It has no selector language, no
positional addressing, no descendant combinators, and no ability to name an
individual document or element instance. If a theme could address position, the
document would have to guarantee position, and appearance would have leaked back
into content.

### 4.2 Reader supremacy is structural

Reader preferences override publisher styling, and there is no mechanism for the
publisher to override back. Not a policy — the format provides no construct that
could express it. Publisher themes are gated by a conformance check because they
are imposed on the reader; reader-installed themes are ungated because they were
chosen.

### 4.3 Format defaults are a theme

The default appearance is itself a normative theme and passes the same
conformance gate as any publisher theme. This prevents the usual outcome where
the defaults are privileged, undocumented, and impossible to reproduce.

### 4.4 One publisher theme, content-hash pinned

A publisher theme is a single same-origin resource, pinned by content hash, and
optional to fetch. It is cached per publisher rather than per document. A
redesign is therefore a republication — which is the correct semantics for
anything signed or archived, and an unwelcome surprise only to people who
expected to restyle history.

### 4.5 Base roles, and how a new element renders in an old theme

**Every semantic role declares the existing base role it inherits from.** A theme
written before a role existed still renders documents that use it, because the
theme's rule for the base role applies to the derived role by inheritance.

This is the theme-side counterpart of §3.6. Degradation keeps an old *client*
working; base-role inheritance keeps an old *theme* working. A proposal that
introduces a role without naming its base role is rejected for the same reason
as one that cannot degrade: it would silently render as unstyled text in every
theme that predates it, and the failure would be invisible to its author.

## 5. Identity, canonical form and the structural hash

### 5.1 The digest is over the tree, not over bytes

`H(node)` is defined recursively over typed nodes: the type, then the fields in
sorted order, then the children in document order, with lengths and separators
included so that no two distinct trees share a preimage. It is never defined
over a serialisation.

The consequence is that the encoding is a revisable transport detail. Canonical
JSON and deterministic CBOR of the same document produce the same digest and the
same Merkle leaves, which is verified rather than asserted
(`tools/structhash.py`). A future encoding does not invalidate an existing
signature.

### 5.2 Why not sign the bytes

Signing bytes means the signature is over a transport artifact. Re-encode,
re-indent, or migrate the store and the signature dies while the document is
unchanged. Archives do all three.

### 5.3 Merkle over block nodes

Block-level nodes are the leaves of a Merkle tree over the document. A single
paragraph is therefore independently provable without transmitting, or even
disclosing, the rest of the document. A 124-block document yields a 224-byte
proof.

Odd nodes are promoted rather than duplicated, which avoids the duplicate-leaf
forgery class, and leaves and internal nodes are domain-separated by distinct
prefixes so that an internal node can never be presented as a leaf.

### 5.4 What "what you see is what you sign" requires

HTML fails this through *content* variance — scripts, third-party resources,
and the state of hosts the publisher does not control — not through font
variance. A format with no author code has content invariance regardless of
rendering. This is why §7 insists on content determinism and explicitly does not
claim pixel determinism.

## 6. The fetch boundary

### 6.1 The rule

A document may name any resource the reader might choose to visit. It may not
name any resource the client fetches without the reader acting.

### 6.2 Enforced by typing, not by policy

Fields the client resolves on its own — `media.src`, `form.action`,
`meta.theme` — are typed `path`: a same-origin relative reference that cannot
express a scheme, an authority, or a leading `//`. A tracking pixel is therefore
not *forbidden*, it is *unrepresentable*. There is no conformant document that
contains one.

M0 found this the hard way: `media.src` was an absolute IRI, which meant the
layer about to freeze permanently permitted a tracking pixel with impeccable
alternative text (`../m0/FINDINGS.md` defect 1).

### 6.3 The generalisation

**A document-controlled string that a client turns into a request is a covert
channel, whether or not it looks like a URL.** The rule is about the field, not
the syntax. Three further client obligations follow, and they are client
conformance requirements rather than document constraints:

1. No speculative resolution of relation targets — no prefetch, no preconnect,
   no DNS warming of anything the reader has not activated.
2. No network lookup of an unknown payload type or an unknown renderer. Renderers
   are named by content hash, never by location, so there is nothing to look up.
3. Language, hyphenation and grammar resources are local only.

### 6.4 The last step is the emitter

Where a document *is* permitted to name a host — `link.href`, reader-initiated —
the scheme is an allowlist rather than a denylist. `javascript:` and `data:` are
the reason: a format that promises no author code and then emits
`<a href="javascript:...">` in its own HTML projection has broken the promise at
the last possible step. The emitter re-checks independently of the validator,
because a projection is the last thing between a document and a browser.

## 7. Determinism

### 7.1 Content determinism, not pixel determinism

What is guaranteed identical across conforming clients is the render tree, not
the rasterisation. Fonts are client-side, declared by role, and never fetched.
Promising identical pixels would require shipping fonts, which would require
fetching them, which would breach §6 to obtain a property nobody actually needs.

### 7.2 No floating point, anywhere

Integers and scaled decimals only, including inside L3 renderer payloads. A
quantity is an integer significand and an integer scale.

One decision closes three questions: the encoding question (no float
representation to agree on), renderer numeric determinism across WASM hosts, and
currency exactness. The first corpus is the first real evidence rather than an
assertion — every monetary amount in it was exactly representable, and the
maximum scale observed was 2.

The corollary found by that corpus: carry the source scale, never normalise it.
Assuming money means two decimal places would have silently rescaled a third of
the corpus and changed the digest of documents whose content had not changed.

## 8. Authoring surfaces

The tree is the document. A surface is an input language, it is non-normative,
and there can be many.

This removes the syntax argument entirely — surfaces can be argued about without
touching the format — and insulates the design from the risk of getting the
first surface wrong. The reference surface should be contained by CommonMark, so
that existing editors, diff tools and review workflows work on day one, with
generic fenced blocks for anything CommonMark cannot express natively.

The test that matters is a fixed point: `text -> tree -> text` returns the
original text. A surface that fails it is lossy, and a lossy surface silently
destroys authored content on the first round trip through any tool.

## 9. Versioning

### 9.1 Freeze the floor, grow the ceiling

L0 is closed permanently. L1 and above are additive only. The version field is
advisory, and clients never negotiate on it.

### 9.2 Additive only

**No element is ever removed, and no element's meaning is ever changed.** Removal
is expressible only as deprecation, which is a documentation state and not a
runtime one: a deprecated element continues to parse, validate and render
exactly as before, forever.

Unknown elements are specified from 1.0 as "render the fallback", so a client
that predates an element behaves identically to one that has chosen not to
implement it. This is the rule that makes §3 load-bearing rather than
decorative, and it is the reason there is no negotiation: there is nothing to
negotiate about.

### 9.3 Why the version field is advisory

A version field that clients act on becomes a compatibility matrix, and a
compatibility matrix becomes the thing implementers get wrong. Here it is
metadata for humans and archives.

### 9.4 A finite vocabulary must be hard to extend

A format whose vocabulary is easy to extend does not have a finite vocabulary.
The finiteness is the product, so the amendment process is deliberately slow:
three real documents that cannot be expressed without the proposal, a mechanical
degradation test, a declared base role, public comment, provisional status, and
two independent implementations before it becomes normative.

### 9.5 Epochs

**If L0 turns out to be wrong, the answer is a new epoch that coexists with this
one — never a change to this one.**

An epoch is a distinct media type with its own frozen L0. Documents in different
epochs are different documents; there is no migration, no upgrade path, and no
implicit conversion. Both epochs remain valid and implementable indefinitely.

This is more expensive than amending L0, and that is the point. Making the
escape hatch costly is what keeps it from being used to avoid hard decisions
now. It also means the promise "an archived document will render in fifty
years" survives being wrong about the design, which a migration path cannot
offer.

## 10. Documents and applications

### 10.1 Applications are a separate media type

A document may link to an application and can never contain one. There is no
inline script element, no expression language, no event model, and no
progressive enhancement seam.

### 10.2 Why the escape hatch is the whole risk

Every constrained format that failed, failed through its escape hatch. The
extension point that was going to be used responsibly became the place all the
complexity went, and the guarantees evaporated because they were guarantees
about a subset nobody stayed inside. The rule is written down precisely because
it will be tested, repeatedly, by people with reasonable-sounding requirements.

### 10.3 The triage rule

> If the interaction needs the **page** to decide when to talk to the server, it
> is an application. If it needs the **reader** to decide, it is a document.

L2 exists to cover the second case and is deliberately incapable of the first.
There is no timer, no lifecycle event, no observer, and no way to express "when
X happens, fetch Y".

### 10.4 The triage rule worked through: customer support

The hardest case, because it is the one every adopter asks for and it looks like
a document until it does not.

| Feature | Verdict | Why |
|---|---|---|
| Knowledge-base article | Document | Static content with structure |
| Article with feedback ("was this helpful?") | Document | L2 form, reader-initiated, one submission |
| Search over articles | Document | The reader submits a query; results are a new document |
| Ticket submission form | Document | Reader-initiated submission, response is a document |
| Ticket status page | Document | Addressable state; the reader reloads or follows a link |
| Ticket status that updates itself | **Application** | The page decides when to poll |
| Live chat with an agent | **Application** | The page decides when to talk to the server |
| Typeahead in the search box | **Application** | A keystroke, not a reader decision, initiates the request |

The line falls between "ticket status page" and "ticket status that updates
itself", and that is a genuinely uncomfortable place for it to fall. It is
nevertheless the right line: the moment the page can decide to talk to the
server, the fetch boundary (§6) is gone, and with it the cost bound and the
"what you see is what you sign" property.

**HTMX is the closest thing in spirit to this design and differs on exactly this
point.** It is an excellent way to build the linked application, and importing
it into the format would end the format. Naming the nearest neighbour and the
precise disagreement is more useful than pretending there is no overlap.

## 11. Transport and the reverse bridge

### 11.1 No forward bridge, ever

There is no mechanism for rendering existing web pages as documents. A converter
would have to guess at structure that HTML does not carry, and every guess would
become a conformance claim the format cannot honour.

### 11.2 The reverse bridge

A publisher serves the canonical tree and a prerendered static HTML projection
from the same URL by content negotiation.

Three consequences, all of them load-bearing for adoption:

1. **Adoption is unilateral.** A publisher benefits on day one with no reader
   doing anything. There is no two-sided market to bootstrap.
2. **The client is not the product.** Nobody has to install anything, which
   removes the usual reason a format like this dies.
3. **The HTML projection inherits the properties.** Because it is generated from
   a tree that cannot express a third-party fetch, the projection cannot contain
   one either.

### 11.3 The stranded reader

Recorded as a weakness rather than solved. The properties most likely to make an
*individual* care — portable themes, reader supremacy, a consistent reading
environment — exist only for native-client users, while §11.2 correctly says
nobody needs a native client. The bridging artifact is a browser extension that
applies reader themes to the HTML projection, and it should come before the
terminal client.

## 12. Non-visual and machine consumption

Because a document carries structure and never appearance, the L0 projection is
normative output rather than best-effort extraction. Every consumer that wants
meaning without presentation reads the same thing: screen readers, terminal
clients, archival indexers, and autonomous agents.

Those are one consumer with one guarantee, not four integrations. This is why
the terminal client (`../docs/ROADMAP.md` M2b) is framed as a conformance proof
rather than a nicety: if a non-visual target needs a special accommodation, the
degradation contract was not doing its job.

Measured against the first corpus: a consumer that wants the meaning of a
published act ingests 1,361 bytes rather than 22,187, of which 89% of the live
payload is markup it pays for and cannot use. The structure it needs is declared
rather than inferred, so there is no heuristic step and no ambiguity introduced
by one — and because block nodes are Merkle-provable (§5.3), a cited paragraph
is verifiable rather than merely quoted.

This was not a design goal. It is the accessibility guarantee restated for a
different consumer, which is the argument for its being a property of the design
rather than a feature attached to it.

## 13. Milestones

Current status is tracked in `../docs/ROADMAP.md`, which is generated from this
list and is the place to look for what is done.

| | Milestone |
|---|---|
| **M0** | Vocabulary register and conformance document, hand-written in canonical form, before any code. Simultaneously the test fixture, the theme validation target, and the thing that forces the vocabulary to close. |
| **M0b** | Corpus coverage against a real public register. |
| **M0b2** | A second corpus in a second genre, exercising what the first did not reach. The last thing gating the L0 freeze. |
| **M0c** | The conformance document written a second time in a surface syntax, compared as a fixed-point test. A fixed-point test, not a taste test. |
| **M1** | Core types, canonical encoding, NFC, structural hash. Parser for L0 and L1. Validator. HTML emitter. Ends with real publishable documents and a page small enough to show someone. |
| **M2** | Theme engine, base role set, three reference themes, theme conformance checker. Browser extension applying reader themes to the HTML projection. Client conformance tests for the unprompted-action rules. |
| **M2b** | Terminal client, as a conformance proof that non-visual targets are siblings rather than accommodations. |
| **M3** | Attestations and a CI action. The point at which it becomes sellable to a public body, and earlier than most people would guess. |
| **M4** | L2 interaction, addressable state, form submission. |
| **M5** | WASM host, anchored text resolution, one reference renderer, build-time execution path. |
| **M6** | Paginated and archival projections with embedded fonts. No longer a research problem, so it can move earlier if an adopter asks. |

## 14. Recorded weaknesses

Kept here rather than in a section that sounds like marketing.

- **The stranded reader** (§11.3).
- **One genre of corpus.** The first corpus did not falsify the vocabulary and
  did not exercise 32 of 52 elements. M0b2 exists for this.
- **Governance is interim.** The licences are irrevocable and the succession
  question has a written answer, but no institution exists.
- **Solo maintainer.** The format is designed to outlive its author; the project
  is not yet.
- **L2 and L3 are unexercised by real documents.** They are specified, they pass
  their own tests, and nothing has published with them.
