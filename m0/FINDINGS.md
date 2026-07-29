# M0 findings

What closing the vocabulary actually surfaced.

M0 is one experiment with one question: write the conformance document *before*
writing any normative text, and see what breaks. The value of the milestone is
not the toolchain, which is throwaway. It is this list, because every entry was
free to fix now and several of them would have been impossible to fix after the
L0 freeze.

---

## Format defects

### 1. `media.src` was an absolute IRI

The layer about to be frozen permanently permitted a tracking pixel with
impeccable alternative text. A document could name any host, and a conforming
client would fetch it before the reader did anything.

**Fix.** `media.src` is typed `path`: a same-origin relative reference that
cannot express a scheme, an authority, or a leading `//`. The same type now
covers `form.action` and `meta.theme`.

**Generalisation, which is the actually valuable part.** A document-controlled
string that a client turns into a request is a covert channel whether or not it
looks like a URL. The rule is therefore about the *field*, not the syntax: a
fetched field cannot express a host at all, so third-party requests are
unrepresentable rather than forbidden. `link.href` remains an absolute IRI
because the client resolves it only on a reader action.

Found by writing out a media example, not by reasoning about the design. That
is the argument for building the fixture before writing the specification.

### 2. `figure` admitted a `rendering` child

`rendering` (L3) declares that it degrades into `figure` (L0). `figure`
permitted `rendering` among its children. Together those two facts mean a
**conforming document projects into a non-conforming one**: a figure containing
a rendering degrades to a figure containing a figure, which the content model
forbids.

**Fix.** `figure` no longer admits `rendering`; a rendering is a sibling, and it
degrades into a figure of its own.

**Generalisation.** The degradation graph and the content models are not
independent. If element `X` degrades to `Y`, then no element permitting `X` as a
child may forbid `Y` as a child. Nothing checked that, and nothing in the design
notes said it. It is now enforced mechanically: `contract` validates the
*projection* as well as the source, which is what caught it.

### 3. Degradation could synthesise empty content

An L2 `field-text` with no value degraded into a paragraph containing a text
node carrying the empty string. The ruleset requires a non-empty string in a
required text field, so the projection failed the format's own R8 check.

**Fix.** Absence of content projects to absence of a node, never to a node
carrying nothing.

**Generalisation.** A degradation is a *total* function from a conforming tree
to a conforming tree. It is not enough for each rule to look reasonable in
isolation; the projection has to be validated, every time, as part of the
contract test rather than as a separate step.

### 4. Ranges and enumerations were being checked on the wrong branch

A field declared `int` with a range, given a string, produced both a type error
and a range error. Diagnostics that multiply per fault make a negative fixture
untestable, because "the ruleset catches all 13 faults" stops being a number you
can assert on.

**Fix.** One fault, one diagnostic. The negative fixture now carries thirteen
deliberate faults across thirteen distinct rules and the ruleset reports exactly
thirteen errors. That count is asserted in CI.

---

## Corpus findings

From the first run against real documents (`corpus/RESULTS.md`, 100 published
acts from the Greek national transparency register).

### 5. Money-shaped objects that contain no money

Real records carry `{"amount": null, "currency": null}` for a salary that does
not apply. A mapper that treats an amount-shaped object as an amount renders
that as `0.00 EUR`, which invents a fact that the source explicitly declines to
state.

**Rule.** An absent amount projects to an absent field. Never to zero. Recorded
here rather than in the register because it is a mapper obligation, not a format
constraint — but it is the kind of thing that turns a verifiable record into a
confidently wrong one.

### 6. Scale is a property of the source, not of the currency

Real amounts arrive at scale 1 and scale 2 in roughly equal numbers. Assuming
"money means two decimal places" would have silently rescaled a third of the
corpus, changing the digest of documents whose content did not change.

**Rule.** Carry the source scale; never normalise a scale on ingest. The maximum
scale observed in the corpus is 2, and nothing needed a float, which is the
first real evidence for the no-floating-point decision rather than an assertion
of it.

### 7. Resolving an identifier must not consume it

The mapper resolved organisation and unit identifiers to their human labels and
dropped the identifiers. Labels are not stable and are not what anything cites.

**Rule.** Carry both. The check that caught this — every non-empty source string
must appear somewhere in the emitted document, as content or as a field value —
turned out to be the single most productive test in the corpus harness, and it
is the same technique as the degradation contract applied to ingest.

---

---

## Second corpus findings

From the second genre (`corpus/RESULTS-rfc.md`, 16 IETF RFCs in RFC 7991 XML
v3). This corpus was chosen because it *could* fail, and it did.

### 8. Superscript is load-bearing, and the register does not have it

**This is the finding that matters, and it falsifies a stated bet.**

`docs/STATE.md` section 6 asks, in as many words, whether superscripts turn out
to be load-bearing in practice, and records that the register bets they are not.

The corpus says they are. `<sup>` occurs **75 times across 16 RFCs**, and every
single occurrence is an exponent: `2<sup>64</sup>`, `2<sup>32</sup>`,
`2<sup>62</sup>`. There are 14 distinct values and all of them are numeric.

Dropping the superscript does not lose formatting. It turns `2^64` into `264`,
inside sentences of the form *"an integer in the range -2^64..2^64-1
inclusive"*. That is a silent numeric corruption in the normative range
specification of a protocol — and it would be produced by a format whose entire
numeric thesis is exactness.

**Status: resolved.** L0 gained a `power` element — option 2 below. Three
candidates were considered:

1. **Add `superscript` and `subscript` to L0.** Cheapest, and wrong on the
   design's own terms: they are appearance, not meaning, and §1 of the design
   notes says appearance is not carried.
2. **Add a semantic inline `power`** with a base and an exponent, degrading to
   `base^exponent`. Design-consistent, and the degradation is not invented —
   the RFC plain-text renderings already use exactly that notation, and RFC 8949
   says so explicitly in its own text.
3. **Decide exponents belong in a payload and render at L3.** Consistent but
   heavy: it makes a number inside a sentence into a renderer invocation.

**Option 2 was taken.** `power` carries a base and an exponent as text (real
exponents include symbolic values such as `n-24`), renders as `base^exponent`,
and is L0 because it is content and L0 is the layer that must carry all
meaning. It is semantic rather than presentational on purpose: a superscript is
appearance, an exponent is meaning, and only the second can live in a format
that does not carry appearance.

The RFC mapper now takes the base token from the preceding text node, so
`2<sup>64</sup>` becomes one semantic node rather than two fragments. After the
fix the RFC corpus needs **no element outside the register at 100%**, and the
register stands at 50 elements (L0 30).

This is the closed vocabulary doing exactly what a closed vocabulary is for:
the bet was written down, a corpus falsified it with a number, and the fix was
made while it was still free. After the freeze the only remedy would have been
a new epoch.

### 9. A cross-reference must not outlive its target

RFC XML anchors far more than a mapping emits ids for: individual paragraphs,
list items, registry rows. The first run produced **826 dangling references** —
pointers that validated as well-formed and resolved to nothing.

**Rule.** A reference whose target is not present in the emitted document
degrades to its own label. This is the intra-document form of the fetch
boundary (§6 of the design notes): a document may not name what is not there.
The validator already had the rule (R11); the mapper had to learn it.

### 10. An empty definition is not an absent term

The mapper initially dropped `term`/`definition` pairs whose definition came out
empty, which silently deleted the term text along with it. Real documents have
index appendices full of terms whose definition is a bare cross-reference.

**Rule.** Absence of a definition is an empty definition, not an absent pair.
Same shape as defect 3: absence of content must project to absence of a node,
but absence of *one part* must not delete the *other part*.

### 11. `item`, `figure` and `table` needed an optional id

Real bibliographies are cited entry by entry, and real specifications
cross-reference figures and tables. None of the three could be a reference
target, because none of them had an `id` field.

Added at L0 as optional. This is a genuine vocabulary gap that only a second
genre could have surfaced: the administrative corpus never cites anything.

---

## Fuzzing findings

`tools/fuzz.py`, 5,000 generated hostile documents per run, deterministic by
seed.

### 12. The library trusted its own input

The first run produced **272 failures in 3,000 cases** — not rejections,
*crashes*. `TypeError: 'int' object is not iterable` from a `c` that was not a
list; `AttributeError: 'str' object has no attribute 'get'` from a child that
was not an object; `TypeError: unhashable type: 'dict'` from a `t` that was not
a string, which reached a dictionary lookup three calls deep.

Every one is a denial of service in any client that embeds the validator, and
none of them were reachable from a fixture written by hand.

**Fix.** The four node accessors are now the trust boundary: they return a
well-typed result for *any* input and never raise. Malformedness is reported as
a diagnostic (R20) rather than as a traceback. After the fix, 5,000 cases
produce zero failures.

**Generalisation.** A conformance ruleset is not a parser. Writing the ruleset
first made it easy to assume the ruleset's own input was already well-formed,
which is exactly the assumption an attacker gets to violate.

---

### 13. Every real figure lacked alternative text

Across 65 graphics in 14 scholarly articles, **zero** carried `<alt-text>` in
the source. All 65 would pass an HTML validator and fail a reader.

`media.alt` is required and non-empty, so none of them is expressible. A
conforming document did not exist until alternative text was supplied, and the
mapper had to derive it from the figure caption.

This is the accessibility claim doing work rather than being asserted, and it
is worth stating precisely: derived alternative text is *worse* than authored
alternative text. The claim is not that the format writes good alt text. It is
that the absence is unrepresentable, so the failure happens at build time in
front of the author instead of silently in front of a reader.

### 14. Two elements were removed, and removal cost nothing

`tab-group` and `tab` survived four corpora without a single instance, and the
one where tabs would live if anywhere — public-sector forms — produced none
either. Five genres, zero occurrences.

They were removed, and `epigraph` followed for the same reason. The register went from 53 elements to 50.

**The reason is not only that they lacked evidence.** Tabs are sections shown
one at a time, which is a theme decision, and this format does not carry
appearance. They degraded to sections anyway, so a publisher who wants tabbed
content writes sections and a theme presents them — which is what should have
happened from the start. The absence of evidence was the prompt to notice a
design error that had been sitting in plain sight.

**The generalisation, now written into governance.** An element that no real
document has ever needed is a liability, not an asset. The amendment process
(`../docs/GOVERNANCE.md` §4) now gates *normative* status on two independent
corpora exercising the element, and keeps the removal path open for everything
that has not passed that gate. This is the structural answer to the way
constrained formats die: they die through the escape hatch, the escape hatch
opens one reasonable-sounding element at a time, and a persuasive argument
cannot satisfy a requirement to produce two unrelated bodies of real documents.

### 15. Public-sector forms are well labelled; the two that were not are unrepresentable

The scholarly corpus found 0 of 65 figures with alternative text. The forms
corpus found the opposite: **2,446 of 2,449 controls carried a real `<label>`**.

That contrast is worth stating rather than hiding. The forms sample is drawn
from GOV.UK, the ECB and comparable bodies, which are among the best-run
publishers in the world for accessibility. It is a *best case*, and it still
contained two controls with no label of any kind — which are, in this format,
unwritable.

It also separates two things HTML conflates. A `placeholder` is not a label: it
disappears on focus and is not reliably announced. The corpus counts
placeholder-rescued and `aria-label`-rescued controls separately, because in
HTML both pass and here both had to be promoted to a real label or dropped.

### 16. `epigraph` was removed after five genres produced none

Five corpora, 138 documents, five markup languages: zero epigraphs.

The gate's answer to that is removal, and the reason it is the right answer is
worth stating because it is counter-intuitive. The obvious move is to go and
find a sixth corpus that contains epigraphs — literary texts would have them.
**That move is exactly what the gate exists to prevent.** Choosing a corpus
because it contains the element you want to justify inverts the test: it stops
measuring whether the vocabulary fits real documents and starts measuring
whether the author can find a document that fits the vocabulary.

Genres are chosen for their importance to the format's purpose. Elements are
kept or removed by what those genres contain. Reversing that order is how a
finite vocabulary stops being finite.

### 17. What chasing a full-marks ratio would have cost

At one point the register stood at 34 of 51 elements passing the two-genre
gate. The natural reading is that full marks is the target and the remainder is
unfinished work. That reading is wrong in three separate ways, and the
distinctions matter more than the number:

- **L3 (2 elements) cannot be evidenced by observation at all.** No existing
  format has typed rendering, so no corpus of existing documents can contain a
  renderer payload. This is why the register marks them `provisional`: they
  need two independent *implementations*, not a corpus. Counting them as a gap
  in corpus coverage is a category error.
- **L2 (8 elements) is one genre wide, not one corpus wide.** Every one is
  exercised by real public forms. What is missing is a second *independent
  publisher family*, which is a real gap and a small one.
- **The rest is two elements at L0 and four at L1**, each of which names the
  genre that would close it: `media` needs a second genre with images,
  `quantity` a second with structured amounts, `article` a second with
  self-contained parts, `contents` any genre with a published table of
  contents.

The number that actually governs the freeze is **L0: 28 of 30 pass the
two-genre gate, and 30 of 30 are exercised by real documents.** L1 and L2 are
additive-only and recoverable; L0 is not.

## Where this leaves the freeze

The first corpus did not falsify the vocabulary. The second one did, on the
exact point the design had written down as a bet, which is the best possible
outcome for a test that cost two days.

| | Corpus 1 (Diavgeia) | Corpus 2 (RFCs) |
|---|---|---|
| Genre | Administrative notices | Standards documents |
| Language | Greek | English |
| Documents produce a conforming tree | 100% | 100% |
| Lose no source string | 100% | **100%** |
| Need no element outside the register | 100% | **100%** (was 44% before `power`) |


**Both gaps are closed.** The exponent became `power`, and a third corpus of
scholarly articles settled `media` (65), `note` (48) and `note-ref` (32).
`../spec/EVIDENCE.md` now records every L0 element as backed by documents nobody
wrote for this project.

What remains is two elements exercised only by the conformance fixture, and
twelve exercised in a single genre. L1 is additive-only
rather than frozen, so an unearned element there is recoverable in a way an L0
one is not. Freezing L0 is now a judgement to take deliberately rather than a
task waiting on evidence.

No element in the register turned out to be *unnecessary*, and the combined
corpora still leave elements untouched by any real document — the L2 and L3
layers in particular are exercised only by the conformance fixture. That remains
the honest weakness: two genres is better than one, and it is not many.
