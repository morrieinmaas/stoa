# SPDX-License-Identifier: Apache-2.0
"""The reverse bridge, running: one URL, four representations, ordinary HTTP.

Design notes section 11.3. Nothing here is new capability -- every
representation is an emitter that already existed. What did not exist was a
URL, and after five corpora there was still nothing anyone could look at.

    python3 tools/serve.py            serve on http://localhost:8080
    python3 tools/serve.py --check    assert what the bridge claims, then exit

The check is the point. Section 11.3 makes three claims that are prose until
something asserts them:

  * no representation can drift, because all of them are generated from the
    tree that is being served;
  * the markdown served converts back to the same structural digest, which is
    a thing markdown extracted from a rendering can never do;
  * the HTML projection cannot name a host, because the tree it came from
    cannot express one.
"""

import argparse
import http.server
import re
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa          # noqa: E402
import htmlemit      # noqa: E402
import surface       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
REG = stoa.Register()

# The name docs/NAME.md already chose: RFC 6838 personal tree, so that
# renaming before standardisation costs nothing. tools/htmlemit.py advertises
# it in every projection it emits.
CANONICAL = "application/prs.stoa"

DOCUMENTS = {
    "/conformance-01": ROOT / "conformance" / "conformance-01.json",
    "/notice-01": ROOT / "corpus" / "sample" / "9ΦΩΓ4691Ω2-ΛΛΧ.json",
}


# --------------------------------------------------------------------------
# representations, all four generated from the same tree
# --------------------------------------------------------------------------

def rep_canonical(doc):
    return stoa.canonical_json(doc)


def rep_html(doc):
    return htmlemit.render(stoa.to_l0(doc, REG)).encode("utf-8")


def rep_markdown(doc):
    return surface.emit(doc).encode("utf-8")


def rep_text(doc):
    return "\n".join(stoa.project_text(stoa.to_l0(doc, REG))).encode("utf-8")


# Order is the server's own preference, used for */* and for a bare request.
# HTML first: a browser that sends */* wants the page, and the whole point of
# the reverse bridge is that nobody has to install anything.
REPRESENTATIONS = [
    ("text/html", rep_html),
    (CANONICAL, rep_canonical),
    ("text/markdown", rep_markdown),
    ("text/plain", rep_text),
]
AVAILABLE = dict(REPRESENTATIONS)

# A reader in a browser cannot set an Accept header, so negotiation alone
# would strand them on the projection. `tools/htmlemit.py` already emits
# <link rel="alternate" href="?form=canonical"> for this reason; the query
# override is what makes that link resolve. It is an override, not a second
# mechanism: it names the same representations, generated the same way.
FORMS = {"canonical": CANONICAL, "html": "text/html",
         "markdown": "text/markdown", "text": "text/plain"}


# --------------------------------------------------------------------------
# content negotiation (RFC 9110 section 12.5.1)
# --------------------------------------------------------------------------

def parse_accept(header):
    """[(media type, q)], best first.

    Ranked by q, then by specificity, then by the order the client wrote them,
    which is what makes `text/html;q=0.1, text/markdown` do the obvious thing.
    """
    ranked = []
    for i, part in enumerate(header.split(",")):
        bits = [b.strip() for b in part.split(";") if b.strip()]
        if not bits:
            continue
        mtype, q = bits[0].lower(), 1.0
        for b in bits[1:]:
            if b.lower().startswith("q="):
                try:
                    q = float(b[2:])
                except ValueError:
                    q = 0.0
        spec = 0 if mtype == "*/*" else (1 if mtype.endswith("/*") else 2)
        ranked.append((-q, -spec, i, mtype, q))
    ranked.sort()
    return [(m, q) for _, _, _, m, q in ranked]


def negotiate(header):
    """The chosen media type, or None for 406."""
    if not header or not header.strip():
        return REPRESENTATIONS[0][0]
    for mtype, q in parse_accept(header):
        if q <= 0:
            continue
        for available, _ in REPRESENTATIONS:
            if (mtype == available or mtype == "*/*"
                    or (mtype.endswith("/*")
                        and available.startswith(mtype[:-1]))):
                return available
    return None


# --------------------------------------------------------------------------
# the index, which is itself a conforming document
# --------------------------------------------------------------------------

def _t(s):
    return {"t": "text", "v": s}


def index_document(host="localhost:8080"):
    """Built from the register and the documents on disk, not hand-written.

    A site whose front door is hand-written HTML would be arguing against
    itself.
    """
    items = []
    for path in sorted(DOCUMENTS):
        doc = stoa.load_document(DOCUMENTS[path])
        items.append({"t": "item", "c": [
            {"t": "paragraph", "c": [
                {"t": "link", "href": path, "c": [_t(doc["title"])]}]}]})
    curl = "\n".join(
        f"curl -H 'Accept: {m}' http://{host}/conformance-01"
        for m, _ in REPRESENTATIONS)
    return {
        "t": "document",
        "id": "urn:stoa:serve-index",
        "lang": "en",
        "title": "The reverse bridge, running",
        "c": [
            {"t": "heading", "level": 1,
             "c": [_t("The reverse bridge, running")]},
            {"t": "paragraph", "c": [_t(
                "Each document below is one URL with four representations, "
                "chosen by ordinary HTTP content negotiation. Every one of "
                "them is generated from the same tree, so none of them can "
                "drift from another. This page is one of those documents.")]},
            {"t": "list", "ordered": False, "c": items},
            {"t": "heading", "level": 2, "c": [_t("Ask for one")]},
            {"t": "code-block", "language": "sh", "c": [_t(curl)]},
            {"t": "paragraph", "c": [_t(
                "The markdown representation is the reference surface, so it "
                "converts back to the same structural digest as the canonical "
                "tree. Markdown extracted from a rendering cannot do that.")]},
        ],
    }


# --------------------------------------------------------------------------
# server
# --------------------------------------------------------------------------

class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "stoa-reverse-bridge/0"
    # Content-Length is set on every response, so 1.1 and its keep-alive are
    # honest here. The default is 1.0, which would be a poor advertisement.
    protocol_version = "HTTP/1.1"
    quiet = False

    def log_message(self, fmt, *args):
        if not self.quiet:
            super().log_message(fmt, *args)

    def _send(self, code, body=b"", ctype=None):
        self.send_response(code)
        # Vary on every response, including the 406: a cache that stored one
        # representation under the bare URL would undo the whole mechanism.
        self.send_header("Vary", "Accept")
        if ctype:
            self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        raw = self.path.split("?", 1)
        path = raw[0].rstrip("/") or "/"
        query = raw[1] if len(raw) > 1 else ""
        if path == "/":
            doc = index_document(self.headers.get("Host", "localhost:8080"))
        elif path in DOCUMENTS:
            doc = stoa.load_document(DOCUMENTS[path])
        else:
            return self._send(404, b"no such document\n", "text/plain")

        form = dict(p.split("=", 1) for p in query.split("&")
                    if "=" in p).get("form")
        if form is not None:
            if form not in FORMS:
                return self._send(
                    404, f"no such form: {form}\n".encode("utf-8"),
                    "text/plain")
            return self._send(200, AVAILABLE[FORMS[form]](doc), FORMS[form])

        chosen = negotiate(self.headers.get("Accept", ""))
        if chosen is None:
            offered = ", ".join(m for m, _ in REPRESENTATIONS)
            return self._send(
                406, f"available: {offered}\n".encode("utf-8"), "text/plain")
        return self._send(200, AVAILABLE[chosen](doc), chosen)

    do_HEAD = do_GET


def serve(port=8080):
    doc = index_document(f"localhost:{port}")
    errs = [d for d in stoa.validate(doc, REG) if d.sev == "error"]
    if errs:
        print("the index is not a conforming document:", file=sys.stderr)
        for d in errs:
            print(f"  {d}", file=sys.stderr)
        return 1
    try:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"cannot bind port {port}: {e}", file=sys.stderr)
        return 1
    print(f"http://localhost:{port}/  ({len(DOCUMENTS)} documents, "
          f"{len(REPRESENTATIONS)} representations each)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


# --------------------------------------------------------------------------
# the check
# --------------------------------------------------------------------------

FAIL = []


def check(name, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'} {name}" + (f"  {detail}" if detail and not cond else ""))
    if not cond:
        FAIL.append(name)


# Constructs that cause a fetch. `href` on an anchor is absent on purpose: a
# link the reader chooses to follow is not a subresource, which is the whole
# distinction the fetch boundary rests on. `<link>` is here only for the rel
# values that fetch -- rel=alternate is metadata, and htmlemit emits one.
FETCHERS = re.compile(
    r"<\s*(?:script|iframe|embed|object|base)\b|@import\b|\burl\s*\(", re.I)
LINK_TAG = re.compile(r"<\s*link\b[^>]*>", re.I)
LINK_REL = re.compile(r"\brel\s*=\s*\"([^\"]*)\"", re.I)
NON_FETCHING_REL = {"alternate", "canonical", "author", "license", "next",
                    "prev", "help", "search", "bookmark", "nofollow"}
FETCHED_ATTR = re.compile(r"\b(?:src|srcset|poster|background)\s*=\s*\"([^\"]*)\"", re.I)
NAMES_A_HOST = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//)")


def get(base, path, accept=None):
    req = urllib.request.Request(base + path)
    if accept is not None:
        req.add_header("Accept", accept)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def run_check(port=0):
    Handler.quiet = True
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    host = f"127.0.0.1:{srv.server_address[1]}"
    base = f"http://{host}"
    print("the reverse bridge, asserted\n")

    # -- the index is a document, not a hand-written page ------------------
    idx = index_document(host)
    errs = [d for d in stoa.validate(idx, REG) if d.sev == "error"]
    check("the index is itself a conforming document", not errs,
          "; ".join(str(d) for d in errs))

    for path in ["/"] + sorted(DOCUMENTS):
        print(f"\n{path}")
        doc = (index_document(host) if path == "/"
               else stoa.load_document(DOCUMENTS[path]))

        # -- one URL, four representations ---------------------------------
        for mtype, _ in REPRESENTATIONS:
            status, hdr, body = get(base, path, mtype)
            check(f"{mtype} is served",
                  status == 200
                  and hdr.get("Content-Type", "").startswith(mtype)
                  and body,
                  f"status {status}, type {hdr.get('Content-Type')!r}")
            check(f"{mtype} varies on Accept",
                  hdr.get("Vary") == "Accept", repr(hdr.get("Vary")))

        # -- negotiation actually negotiates -------------------------------
        cases = [
            ("q-values are honoured over header order",
             "text/html;q=0.1, text/markdown;q=0.9", "text/markdown"),
            ("a bare */* gets the page", "*/*", "text/html"),
            ("no Accept header gets the page", None, "text/html"),
            ("a type wildcard resolves within its type", "text/*", "text/html"),
            ("an explicit q=0 is a refusal",
             "text/html;q=0, text/plain", "text/plain"),
        ]
        for name, accept, want in cases:
            _, hdr, _ = get(base, path, accept)
            check(name, hdr.get("Content-Type", "").startswith(want),
                  f"got {hdr.get('Content-Type')!r}, wanted {want}")

        status, hdr, _ = get(base, path, "image/png")
        check("an unavailable type is 406, still varying on Accept",
              status == 406 and hdr.get("Vary") == "Accept", f"status {status}")

        # -- the HTML projection cannot name a host ------------------------
        _, _, html = get(base, path, "text/html")
        html = html.decode("utf-8")
        found = FETCHERS.findall(html)
        for tag in LINK_TAG.findall(html):
            rel = LINK_REL.search(tag)
            rels = set((rel.group(1) if rel else "").lower().split())
            if not rels or (rels - NON_FETCHING_REL):
                found.append(tag)
        check("the HTML names no stylesheet, script, frame or font",
              not found, f"found {found}")
        hosts = [v for v in FETCHED_ATTR.findall(html) if NAMES_A_HOST.match(v)]
        check("no subresource in the HTML names a host", not hosts,
              f"found {hosts}")

        # -- the alternate the projection advertises actually resolves -----
        alts = [t for t in LINK_TAG.findall(html) if "alternate" in t.lower()]
        check("the HTML advertises the canonical form", len(alts) == 1,
              f"found {alts}")
        for form, mtype in sorted(FORMS.items()):
            _, hdr, body = get(base, f"{path}?form={form}"
                               if path != "/" else f"/?form={form}")
            check(f"?form={form} reaches {mtype} without an Accept header",
                  hdr.get("Content-Type", "").startswith(mtype)
                  and body == AVAILABLE[mtype](doc),
                  f"got {hdr.get('Content-Type')!r}")

        # -- the markdown converts back ------------------------------------
        _, _, md = get(base, path, "text/markdown")
        reparsed = surface.parse(md.decode("utf-8"))
        check("the markdown served reproduces the structural digest",
              stoa.digest_hex(reparsed) == stoa.digest_hex(doc),
              f"{stoa.digest_hex(reparsed)[:16]} != {stoa.digest_hex(doc)[:16]}")
        check("the markdown served is itself conforming",
              not [d for d in stoa.validate(reparsed, REG) if d.sev == "error"])

        # -- no representation can drift -----------------------------------
        _, _, canon = get(base, path, CANONICAL)
        check("the canonical representation is the document on the wire",
              canon == stoa.canonical_json(doc))
        _, _, text = get(base, path, "text/plain")
        check("the text representation is the normative L0 projection",
              text == rep_text(doc))

    srv.shutdown()
    print()
    if FAIL:
        print(f"{len(FAIL)} FAILED: {', '.join(FAIL)}")
        return 1
    print("the bridge holds")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="assert the bridge's claims and exit")
    ap.add_argument("--port", type=int, default=8080)
    a = ap.parse_args(argv[1:])
    return run_check(0) if a.check else serve(a.port)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
