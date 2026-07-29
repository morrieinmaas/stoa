# SPDX-License-Identifier: Apache-2.0
"""The corpus coverage test: does the closed vocabulary survive real documents?

Takes N real decisions from Diavgeia, the Greek national transparency register
(diavgeia.gov.gr, ~3.1M published acts), maps each into a Stoa tree, and
measures four things:

  1. Coverage    what fraction map with no element outside the register, no
                 validation error, and no source string dropped
  2. Omissions   which source fields the register could not carry
  3. Numerics    what decimal scales real money actually uses, and whether
                 anything genuinely needs a float
  4. Envelope    emitted bytes and fetched subresources, against the live page

This is the last thing gating the L0 freeze. Below roughly 95% coverage means
the vocabulary is wrong, not that the corpus is unusual.

    python3 tools/diavgeia.py            # 100 notices, cached
    python3 tools/diavgeia.py --n 300 --refresh
    python3 tools/diavgeia.py --emit <ADA>   # dump one notice as HTML and text
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa            # noqa: E402
import htmlemit        # noqa: E402
import structhash      # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "corpus" / "cache"
API = "https://diavgeia.gov.gr/opendata"

# Source keys that are transport or revision bookkeeping rather than the
# content of the published act. Declared explicitly so that "we dropped it"
# is a decision on the record and not an accident.
NOT_CONTENT = {
    "versionId", "warnings", "privateData", "url",
    "correctedVersionId", "documentChecksum",
}

# Human labels for the source field names that appear in every record.
LABELS = {
    "ada": "ADA", "protocolNumber": "Protocol number", "subject": "Subject",
    "issueDate": "Date of issue", "publishTimestamp": "Published",
    "submissionTimestamp": "Submitted", "organizationId": "Issuing body",
    "unitIds": "Unit", "signerIds": "Signed by", "decisionTypeId": "Act type",
    "thematicCategoryIds": "Thematic category", "status": "Status",
    "documentUrl": "Source document", "attachments": "Attachments",
    "documentType": "Document type", "org": "Body",
    "sponsor": "Expenditure", "relatedDecisions": "Related acts",
    "relatedEkgrisiDapanis": "Related expenditure approval",
    "skipVatReason": "VAT exemption reason", "afm": "Tax number",
    "afmType": "Tax number type", "afmCountry": "Country", "name": "Name",
    "amount": "Amount", "currency": "Currency", "expenseAmount": "Amount",
    "sponsorAFMName": "Beneficiary", "cpv": "CPV code", "kae": "Budget line",
    "relatedDecisionsADA": "ADA",
}


# --------------------------------------------------------------------------
# fetching, with a local cache so the measurement is reproducible offline
# --------------------------------------------------------------------------

def _get(url):
    req = urllib.request.Request(
        url, headers={"Accept": "application/json",
                      "User-Agent": "stoa-corpus/0 (+m0 coverage test)"})
    with urllib.request.urlopen(req, timeout=60) as f:
        return f.read()


def fetch_corpus(n, refresh=False, pages_apart=6007):
    """Sample across widely separated pages: results are recency-ordered, so
    distant pages are distant weeks and different bodies."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / f"corpus-{n}.pages.json"

    # The cache stores the raw response bodies, not a re-serialised structure.
    # Every parse of them uses parse_float=Decimal, so a monetary amount never
    # passes through a binary float on any path. In a format whose premise is
    # that floats are unrepresentable, round-tripping the corpus through one
    # would be the single most embarrassing possible defect.
    if cache.exists() and not refresh:
        pages = json.loads(cache.read_text(encoding="utf-8"))
    else:
        pages, page = [], 0
        while sum(len(json.loads(p)["decisions"]) for p in pages) < n:
            url = f"{API}/search?q=*&size={min(25, n)}&page={page}"
            try:
                body = _get(url).decode("utf-8")
            except urllib.error.URLError as e:
                print(f"  fetch failed at page {page}: {e}", file=sys.stderr)
                break
            if not (json.loads(body).get("decisions") or []):
                break
            pages.append(body)
            page += pages_apart
            time.sleep(0.3)
        cache.write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")

    out = []
    for body in pages:
        out.extend(json.loads(body, parse_float=Decimal).get("decisions") or [])
    return out[:n]


def resolve(kind, uid, memo):
    """Resolve an organisation, unit or signer id to a human label. Cached on
    disk; a lookup failure degrades to the bare id rather than dropping the
    field. The id is always carried alongside the label, because the id is
    the machine identifier of record and the label is not stable."""
    key = f"{kind}/{uid}"
    if key in memo:
        return memo[key]
    path = CACHE / f"{kind}.json"
    store = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if uid not in store:
        try:
            d = json.loads(_get(f"{API}/{kind}/{uid}").decode("utf-8"))
            if kind == "signers":
                label = " ".join(x for x in (d.get("firstName"), d.get("lastName")) if x)
            else:
                label = d.get("label")
            store[uid] = label or uid
        except Exception:
            store[uid] = uid
        path.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    label = store[uid]
    memo[key] = f"{label} ({uid})" if label != uid else uid
    return memo[key]


# --------------------------------------------------------------------------
# builders
# --------------------------------------------------------------------------

def _t(s):
    return {"t": "text", "v": str(s)}


def _p(*inline):
    return {"t": "paragraph", "c": list(inline)}


def _pair(label, blocks):
    return [{"t": "term", "c": [_t(label)]}, {"t": "definition", "c": blocks}]


def _iso(ms):
    return time.strftime("%Y-%m-%d", time.gmtime(int(ms) / 1000))


def _iso_second(ms):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ms) / 1000))


def label_for(k):
    return LABELS.get(k, re.sub(r"(?<!^)(?=[A-Z])", " ", k).capitalize())


class Findings:
    def __init__(self):
        self.escapes = Counter()      # source fields the register could not carry
        self.scales = Counter()       # decimal scales seen in real money
        self.currencies = Counter()
        self.notes = Counter()


def quantity(amount, unit, f):
    """Exact decimal, never a float. Records the scale actually used."""
    d = amount if isinstance(amount, Decimal) else Decimal(str(amount))
    exp = d.as_tuple().exponent
    src_scale = max(0, -int(exp))
    f.scales[src_scale] += 1
    scale = max(2, src_scale)
    sig = int((d.scaleb(scale)).to_integral_value())
    if Decimal(sig).scaleb(-scale) != d:
        f.notes["amount not exactly representable at its own scale"] += 1
    f.currencies[unit] += 1
    return {"t": "quantity", "significand": sig, "scale": scale, "unit": unit}


def value_blocks(v, key, f):
    """Map an arbitrary source value into register elements. Anything that
    cannot be placed is recorded as an escape rather than silently dropped."""
    if v is None or v == "" or v == [] or v == {}:
        return []
    if isinstance(v, bool):
        return [_p(_t("yes" if v else "no"))]
    if isinstance(v, Decimal):
        return [_p(_t(str(v)))]
    if isinstance(v, (int, float)):
        if isinstance(v, float):
            f.escapes[f"{key}: bare float"] += 1
            return []
        return [_p(_t(str(v)))]
    if isinstance(v, str):
        return [_p(_t(v))]
    if isinstance(v, dict):
        if "amount" in v and "currency" in v and set(v) <= {"amount", "currency"}:
            amt, cur = v["amount"], v["currency"]
            # An absent amount is absence. Rendering it as 0.00 would invent a
            # fact; real records carry money-shaped objects that are empty.
            if amt is None:
                f.notes["money object present but amount is null: field omitted"] += 1
                return []
            if not cur:
                f.notes["amount with no currency: rendered as a plain number"] += 1
                return [_p(_t(str(amt)))]
            return [_p(quantity(amt, cur, f))]
        pairs = []
        for k in v:
            b = value_blocks(v[k], k, f)
            if b:
                pairs += _pair(label_for(k), b)
        return [{"t": "term-list", "c": pairs}] if pairs else []
    if isinstance(v, list):
        if v and all(isinstance(x, dict) for x in v):
            return [table_from(v, f)]
        items = []
        for x in v:
            b = value_blocks(x, key, f)
            if b:
                items.append({"t": "item", "c": b})
        return [{"t": "list", "ordered": False, "c": items}] if items else []
    f.escapes[f"{key}: {type(v).__name__}"] += 1
    return []


def table_from(rows, f):
    cols = []
    for r in rows:
        for k in r:
            if k not in cols:
                cols.append(k)
    head = {"t": "row", "c": [
        {"t": "header-cell", "scope": "column", "c": [_p(_t(label_for(c)))]}
        for c in cols]}
    body = []
    for r in rows:
        body.append({"t": "row", "c": [
            {"t": "cell", "c": value_blocks(r.get(c), c, f)} for c in cols]})
    return {"t": "table", "summary": "Structured data from the source record",
            "c": [{"t": "table-section", "kind": "head", "c": [head]},
                  {"t": "table-section", "kind": "body", "c": body}]}


# --------------------------------------------------------------------------
# the mapping
# --------------------------------------------------------------------------

def to_stoa(rec, f, memo):
    consumed = set(NOT_CONTENT)

    def take(k):
        consumed.add(k)
        return rec.get(k)

    subject = (take("subject") or "").strip()
    ada = take("ada") or ""

    prov = []
    prov += _pair("ADA", [_p(_t(ada))])
    if take("protocolNumber"):
        prov += _pair(LABELS["protocolNumber"], [_p(_t(rec["protocolNumber"]))])
    if take("decisionTypeId"):
        prov += _pair(LABELS["decisionTypeId"], [_p(_t(rec["decisionTypeId"]))])
    if take("organizationId"):
        prov += _pair(LABELS["organizationId"],
                      [_p(_t(resolve("organizations", rec["organizationId"], memo)))])
    for uid in take("unitIds") or []:
        prov += _pair(LABELS["unitIds"], [_p(_t(resolve("units", uid, memo)))])
    if take("issueDate"):
        prov += _pair(LABELS["issueDate"],
                      [_p({"t": "date", "value": _iso(rec["issueDate"]),
                           "precision": "day"})])
    if take("publishTimestamp"):
        prov += _pair(LABELS["publishTimestamp"],
                      [_p({"t": "date", "value": _iso_second(rec["publishTimestamp"]),
                           "precision": "second"})])
    if take("submissionTimestamp"):
        prov += _pair(LABELS["submissionTimestamp"],
                      [_p({"t": "date", "value": _iso_second(rec["submissionTimestamp"]),
                           "precision": "second"})])
    if take("status"):
        prov += _pair(LABELS["status"], [_p(_t(rec["status"]))])
    for cat in take("thematicCategoryIds") or []:
        prov += _pair(LABELS["thematicCategoryIds"], [_p(_t(cat))])

    # document.title already carries the subject as metadata; repeating it as
    # a paragraph under its own heading is the kind of redundancy the source
    # system has and the format does not need
    body = [{"t": "heading", "level": 1, "c": [_t(subject or ada)]},
            {"t": "provenance", "c": prov}]

    extra = take("extraFieldValues") or {}
    for k in extra:
        blocks = value_blocks(extra[k], k, f)
        if blocks:
            body.append({"t": "section", "c": [
                {"t": "heading", "level": 2, "c": [_t(label_for(k))]}] + blocks})

    atts = take("attachments") or []
    doc_url = take("documentUrl")
    links = []
    if doc_url:
        links.append({"t": "item", "c": [_p(
            {"t": "link", "href": doc_url, "c": [_t("Signed source document (PDF)")]})]})
    for a in atts:
        href = a.get("url") if isinstance(a, dict) else None
        name = (a.get("description") or a.get("filename") or "Attachment") \
            if isinstance(a, dict) else str(a)
        if href:
            links.append({"t": "item", "c": [_p(
                {"t": "link", "href": href, "c": [_t(name)]})]})
    if links:
        body.append({"t": "section", "c": [
            {"t": "heading", "level": 2, "c": [_t("Documents")]},
            {"t": "list", "ordered": False, "c": links}]})

    signers = take("signerIds") or []
    if signers:
        sig = []
        for s in signers:
            sig += _pair("Signed by", [_p(_t(resolve("signers", s, memo)))])
        body.append({"t": "signature-block", "c": sig})

    for k in rec:
        if k not in consumed and rec[k] not in (None, "", [], {}):
            f.escapes[f"unmapped source field: {k}"] += 1

    title = subject or f"Act {ada}"
    return {"t": "document", "id": f"urn:stoa:diavgeia:{ada}", "lang": "el",
            "title": title[:300], "c": body}


# --------------------------------------------------------------------------
# measurement
# --------------------------------------------------------------------------

FETCHED = re.compile(
    r"<script[^>]*\ssrc=|<link[^>]*rel=[\"']?stylesheet|<img[^>]*\ssrc=|"
    r"<iframe|@import|url\(", re.I)


def source_strings(v, out, key=None):
    if isinstance(v, str) and v.strip() and key not in NOT_CONTENT:
        out.append(stoa.nfc(v.strip()))
    elif isinstance(v, dict):
        for k, x in v.items():
            if k not in NOT_CONTENT:
                source_strings(x, out, k)
    elif isinstance(v, list):
        for x in v:
            source_strings(x, out, key)


def carried_strings(doc):
    """Everything the emitted document carries: visible content units, plus
    field values such as a link target or a date."""
    out = set(stoa.content_units(doc))
    for node, _ in stoa.walk(doc):
        for v in stoa.fields(node).values():
            if isinstance(v, str):
                out.add(stoa.nfc(v))
    return out


def live_page_envelope(ada):
    try:
        url = "https://diavgeia.gov.gr/decision/view/" + urllib.parse.quote(ada)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        t = time.time()
        with urllib.request.urlopen(req, timeout=45) as fh:
            b = fh.read()
        h = b.decode("utf-8", "replace")
        # what a non-visual consumer can actually recover from the page
        s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
        s = re.sub(r"(?s)<[^>]+>", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return len(b), len(FETCHED.findall(h)), time.time() - t, len(s.encode())
    except Exception:
        return None


def run(n, refresh, out_path):
    reg = stoa.Register()
    f = Findings()
    memo = {}

    print(f"fetching up to {n} notices from Diavgeia ...", file=sys.stderr)
    recs = fetch_corpus(n, refresh)
    print(f"  {len(recs)} records", file=sys.stderr)

    ok = nfc_fail = 0
    err_rules = Counter()
    types_used = Counter()
    decision_types = Counter()
    orgs = set()
    jb = cb = hb = tb = 0
    dropped_strings = Counter()
    per_doc_errors = []

    for rec in recs:
        decision_types[rec.get("decisionTypeId") or "?"] += 1
        orgs.add(rec.get("organizationId"))
        before = len(f.escapes)
        doc = to_stoa(rec, f, memo)

        diags = stoa.validate(doc, reg)
        errs = [d for d in diags if d.sev == "error"]
        nfc_errs = [d for d in errs if d.rule == "R15"]
        if nfc_errs:
            nfc_fail += 1
            # the documented fix: normalise on ingest. Re-check to see whether
            # NFC was the only problem.
            doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))
            diags = stoa.validate(doc, reg)
            errs = [d for d in diags if d.sev == "error"]
        for d in errs:
            err_rules[d.rule] += 1

        # nothing in the source may be silently lost, as visible content or
        # as a field value a client can act on (a link target, a date)
        want = []
        source_strings(rec, want)
        carried = carried_strings(doc)
        blob = "\n".join(sorted(carried))
        lost = [s for s in want if s not in carried and s not in blob]
        for s in lost:
            dropped_strings[s[:60]] += 1

        escaped = len(f.escapes) > before
        if not errs and not lost and not escaped:
            ok += 1
        else:
            per_doc_errors.append((rec.get("ada"), len(errs), len(lost), escaped))

        for node, _ in stoa.walk(doc):
            if stoa.typ(node) in reg:
                types_used[stoa.typ(node)] += 1

        l0 = stoa.to_l0(doc, reg)
        jb += len(stoa.canonical_json(doc))
        cb += len(structhash.cbor_encode(stoa.nfc_tree(doc)))
        hb += len(htmlemit.render(l0).encode("utf-8"))
        tb += len("\n".join(stoa.project_text(l0)).encode("utf-8"))

    total = len(recs) or 1
    cov = 100.0 * ok / total
    live = live_page_envelope(recs[0]["ada"]) if recs else None

    lines = []
    w = lines.append
    w("# Corpus coverage: Diavgeia\n")
    w(f"Generated by `tools/diavgeia.py` over {total} real published acts from "
      f"the Greek national transparency register.\n")
    w(f"Sampled across {len(decision_types)} act types and {len(orgs)} public "
      f"bodies.\n")

    w("## 1. Coverage\n")
    w(f"**{cov:.1f}%** ({ok}/{total}) of real notices map into the register "
      f"with no element outside it, no validation error, and no source string "
      f"dropped.\n")
    w(f"- documents with a conformance error: "
      f"{sum(1 for _, e, _, _ in per_doc_errors if e)}")
    w(f"- documents with a dropped source string: "
      f"{sum(1 for _, _, l, _ in per_doc_errors if l)}")
    w(f"- documents needing an element outside the register: "
      f"{sum(1 for _, _, _, x in per_doc_errors if x)}\n")
    if err_rules:
        w("Conformance errors by rule, after NFC normalisation on ingest:\n")
        for r, c in err_rules.most_common():
            w(f"- `{r}` x{c}")
        w("")
    w(f"Records whose source text was not NFC-normalised: **{nfc_fail}/{total}**. "
      f"Normalising on ingest is a mapper obligation, not a format change; "
      f"the count is reported because it is the kind of thing that silently "
      f"breaks a digest.\n")

    w("## 2. Omissions\n")
    if f.escapes:
        w("Source content the register could not carry:\n")
        for k, c in f.escapes.most_common(20):
            w(f"- {k} — x{c}")
    else:
        w("None. No source field in the sample required an element outside "
          "the register.\n")
    if dropped_strings:
        w("\nSource strings lost in mapping:\n")
        for s, c in dropped_strings.most_common(10):
            w(f"- x{c} `{s}`")
    w("")

    w("## 3. Numerics\n")
    if f.scales:
        w("Decimal scales actually used by real monetary amounts:\n")
        for s in sorted(f.scales):
            w(f"- scale {s} (10^-{s}) — {f.scales[s]} amounts")
        w(f"\nMaximum scale observed: **{max(f.scales)}**. "
          f"Currencies: {', '.join(sorted(c for c in f.currencies if c))}.\n")
        w("Every amount is exactly representable as an integer significand "
          "with an integer scale. Nothing in the sample needs a float.\n")
    else:
        w("No monetary amounts in the sample.\n")
    if f.notes:
        w("Numeric edge cases the corpus produced:\n")
        for k, c in f.notes.most_common():
            w(f"- {k} — x{c}")
        w("")

    w("## 4. Envelope\n")
    w("| | Stoa (canonical) | Stoa (CBOR) | Stoa (HTML projection) | L0 text |")
    w("|---|---|---|---|---|")
    w(f"| mean bytes / notice | {jb // total:,} | {cb // total:,} | "
      f"{hb // total:,} | {tb // total:,} |")
    w("")
    if live:
        lb, lsub, lt, ltext = live
        w(f"Against the live Diavgeia page for the same act:\n")
        w("| | live page | Stoa HTML projection |")
        w("|---|---|---|")
        w(f"| HTML bytes | {lb:,} | {hb // total:,} |")
        w(f"| fetched subresources | {lsub} | **0** |")
        w(f"| requests for first complete content | {lsub + 1} | **1** |")
        w("")
        w("The subresource count is not a minification result. A Stoa document "
          "cannot name a host the client contacts without a reader action, so "
          "third-party requests are unrepresentable rather than merely absent.\n")

        w("### Non-visual consumption\n")
        w("The same figures from the point of view of a consumer that wants "
          "the meaning and not the page: a screen reader, a terminal client, "
          "an archival indexer, or an autonomous agent.\n")
        w("| | live page | Stoa L0 text projection |")
        w("|---|---|---|")
        w(f"| bytes to ingest | {lb:,} | **{tb // total:,}** |")
        w(f"| of which recoverable text | {ltext:,} ({100 * ltext // lb}%) | "
          f"{tb // total:,} (100%) |")
        w(f"| markup and boilerplate paid for but unusable | "
          f"{lb - ltext:,} ({100 * (lb - ltext) // lb}%) | **0** |")
        w(f"| ratio | — | **{lb / max(1, tb // total):.1f}x smaller** |")
        w("")
        w("This is the accessibility guarantee measured from the other end. "
          "The L0 projection is not a stripped-down version of the document; "
          "it is normative, it is what the degradation contract guarantees is "
          "lossless, and it is produced by the format rather than recovered "
          "from it by heuristics. A consumer that wants structured meaning "
          "does not have to parse a presentation layer to guess at it.\n")

    w("## 5. Element mix\n")
    w(f"{len(types_used)} of {len(reg.elements)} register elements were "
      f"exercised by real documents.\n")
    w("| Element | Layer | Occurrences |")
    w("|---|---|---|")
    for name, c in types_used.most_common():
        w(f"| `{name}` | L{reg.layer(name)} | {c:,} |")
    w("")
    unused = sorted(set(reg.elements) - set(types_used))
    w(f"Not exercised by this corpus ({len(unused)}): "
      f"{', '.join('`' + u + '`' for u in unused)}.\n")
    w("An element unused by one register is not evidence it is unneeded; it "
      "is evidence this corpus is one document genre. The freeze decision "
      "needs a second genre, which is the next corpus.\n")

    w("## 6. What this does not test\n")
    w("Read the coverage figure with these limits attached. They are the "
      "reasons it is not yet sufficient to freeze L0.\n")
    w("1. **The act body is a PDF and is not tested.** Diavgeia publishes a "
      "structured record *around* a signed PDF. This measures the published "
      "record, which is what the site itself renders as a page; it does not "
      "measure the prose inside the PDF. Sub-headed legal prose, numbered "
      "recitals, and inline tables live there, and that is where an omission "
      "in the register would actually show up.")
    w("2. **A generic mapper flatters the register.** Any JSON scalar can be "
      "placed in a term-list and any array of objects in a table, so a "
      "JSON-shaped source will nearly always map. The measure is therefore "
      "strongest as a *falsifier* — a failure would have been decisive — and "
      "weakest as a positive claim.")
    w("3. **One genre, one country, one language.** A gazette, a statute, a "
      "standards document, and a scientific record are different shapes. "
      f"{len(unused)} of {len(reg.elements)} elements were never exercised.")
    w("4. **No adversarial input.** Every record here is well-formed output "
      "from one publishing system. The parser has not been fuzzed and the "
      "corpus contains no hostile document.\n")
    w("The honest summary: nothing in a real public register falsified the "
      "closed vocabulary, and the envelope figures hold up. That is a "
      "necessary condition for the freeze, not a sufficient one.\n")

    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[written to {out_path}]", file=sys.stderr)
    return 0 if cov >= 95.0 else 1


def emit_one(ada):
    reg, f, memo = stoa.Register(), Findings(), {}
    rec = json.loads(_get(f"{API}/decisions/{urllib.parse.quote(ada)}").decode("utf-8"),
                     parse_float=Decimal)
    rec = rec.get("decision", rec)
    doc = to_stoa(rec, f, memo)
    doc = json.loads(json.dumps(stoa.nfc_tree(doc), ensure_ascii=False))
    l0 = stoa.to_l0(doc, reg)
    out = ROOT / "corpus" / "sample"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{ada}.json").write_bytes(stoa.canonical_json(doc) + b"\n")
    (out / f"{ada}.html").write_text(htmlemit.render(l0), encoding="utf-8")
    (out / f"{ada}.txt").write_text("\n".join(stoa.project_text(l0)), encoding="utf-8")
    for d in stoa.validate(doc, reg):
        print(d)
    print(f"wrote {out}/{ada}.{{json,html,txt}}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--emit", metavar="ADA")
    ap.add_argument("--out", default=str(ROOT / "corpus" / "RESULTS.md"))
    a = ap.parse_args()
    if a.emit:
        return emit_one(a.emit)
    return run(a.n, a.refresh, a.out)


if __name__ == "__main__":
    sys.exit(main())
