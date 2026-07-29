# SPDX-License-Identifier: Apache-2.0
"""The reverse bridge: an L0 tree to static HTML, as a fold over the tree.

One function per element and nothing else. The emitted page references no
script, no stylesheet, no font file, and no third-party host, so it costs
exactly one request. That is not a minification result, it is what the
vocabulary makes expressible.

A publisher serves this projection and the canonical tree from the same URL by
content negotiation, which is why adoption is unilateral and there is no
two-sided market to bootstrap.
"""

from html import escape

import stoa

VOID = {"media", "line-break", "note-ref"}


def emit(node, out=None):
    if out is None:
        out = []
    fn = HANDLERS.get(stoa.typ(node), _generic)
    fn(node, out)
    return out


def kids(node, out):
    for c in stoa.children(node):
        emit(c, out)


def _generic(node, out):
    kids(node, out)


def _document(node, out):
    out.append(f'<!DOCTYPE html>\n<html lang="{escape(node["lang"], True)}">\n<head>')
    out.append('<meta charset="utf-8">')
    out.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    out.append(f"<title>{escape(node['title'])}</title>")
    out.append(f'<link rel="alternate" type="application/prs.stoa" href="?form=canonical">')
    out.append("</head>\n<body>")
    kids(node, out)
    out.append("</body>\n</html>")


def _wrap(tag, attrs=()):
    def fn(node, out):
        a = "".join(
            f' {k}="{escape(str(node[f]), True)}"'
            for f, k in attrs if node.get(f) is not None
        )
        out.append(f"<{tag}{a}>")
        kids(node, out)
        out.append(f"</{tag}>")
    return fn


def _heading(node, out):
    lvl = min(max(node.get("level", 1), 1), 6)
    out.append(f"<h{lvl}>")
    kids(node, out)
    out.append(f"</h{lvl}>")


def _list(node, out):
    tag = "ol" if node.get("ordered") else "ul"
    start = f' start="{node["start"]}"' if node.get("start") is not None else ""
    out.append(f"<{tag}{start}>")
    kids(node, out)
    out.append(f"</{tag}>")


def _text(node, out):
    out.append(escape(str(node.get("v", ""))))


def _code_block(node, out):
    inner = "".join(str(c.get("v", "")) for c in stoa.children(node))
    cls = f' class="language-{escape(node["language"], True)}"' if node.get("language") else ""
    out.append(f"<pre><code{cls}>{escape(inner)}</code></pre>")


def _media(node, out):
    src, alt = escape(node["src"], True), escape(node.get("alt", ""), True)
    kind = node.get("kind")
    if kind == "image":
        out.append(f'<img src="{src}" alt="{alt}">')
    else:
        out.append(f'<{kind} controls src="{src}"></{kind}><p>{alt}</p>')


def _quantity(node, out):
    v = stoa.format_quantity(node)
    out.append(f'<data value="{escape(v, True)}">{escape(v)}</data>')


def _power(node, out):
    # <sup> is presentation, which the document cannot carry but a rendering
    # of it can. The data attribute keeps the plain-text form recoverable.
    b, e = escape(str(node.get("base", ""))), escape(str(node.get("exponent", "")))
    out.append(f'<span data-power="{b}^{e}">{b}<sup>{e}</sup></span>')


def _date(node, out):
    v = escape(str(node.get("value", "")), True)
    out.append(f'<time datetime="{v}">{v}</time>')


def _cell(tag):
    def fn(node, out):
        a = ""
        for f, k in (("colspan", "colspan"), ("rowspan", "rowspan"), ("scope", "scope")):
            if node.get(f) is not None:
                a += f' {k}="{escape(str(node[f]), True)}"'
        out.append(f"<{tag}{a}>")
        kids(node, out)
        out.append(f"</{tag}>")
    return fn


def _link(node, out):
    href = node.get("href", "")
    if not stoa.safe_iri(href):
        # A scheme the format does not permit is not emitted at all. The link
        # degrades to its own text, which is the safe direction. Independent of
        # the validator on purpose: this is the last step before a browser.
        kids(node, out)
        return
    # rel=noreferrer because the fetch boundary is a client obligation too:
    # following a link must not leak where the reader came from
    out.append(f'<a href="{escape(href, True)}" rel="noreferrer">')
    kids(node, out)
    out.append("</a>")


def _reference(node, out):
    out.append(f'<a href="#{escape(node["target"], True)}">')
    kids(node, out)
    out.append("</a>")


def _note_ref(node, out):
    t = escape(node["target"], True)
    out.append(f'<sup><a href="#{t}">{t}</a></sup>')


def _note(node, out):
    out.append(f'<aside id="{escape(node["id"], True)}" role="note">')
    kids(node, out)
    out.append("</aside>")


def _table(node, out):
    out.append("<table>")
    if node.get("summary"):
        out.append(f"<caption>{escape(node['summary'])}</caption>")
    rows = [c for c in stoa.children(node) if stoa.typ(c) == "row"]
    for c in stoa.children(node):
        if stoa.typ(c) == "caption" and not node.get("summary"):
            out.append("<caption>")
            kids(c, out)
            out.append("</caption>")
    if rows:
        out.append("<tbody>")
        for r in rows:
            emit(r, out)
        out.append("</tbody>")
    out.append("</table>")


HANDLERS = {
    "document": _document,
    "section": _wrap("section", [("id", "id"), ("lang", "lang")]),
    "heading": _heading,
    "paragraph": _wrap("p"),
    "list": _list,
    "item": _wrap("li"),
    "term-list": _wrap("dl"),
    "term": _wrap("dt"),
    "definition": _wrap("dd"),
    "quote": _wrap("blockquote", [("source", "cite")]),
    "code-block": _code_block,
    "note": _note,
    "figure": _wrap("figure"),
    "caption": _wrap("figcaption"),
    "media": _media,
    "table": _table,
    "row": _wrap("tr"),
    "cell": _cell("td"),
    "header-cell": _cell("th"),
    "text": _text,
    "emphasis": _wrap("em"),
    "strong": _wrap("strong"),
    "code": _wrap("code"),
    "link": _link,
    "reference": _reference,
    "note-ref": _note_ref,
    "quantity": _quantity,
    "power": _power,
    "date": _date,
    "line-break": lambda n, o: o.append("<br>"),
}


def render(l0_tree):
    return "".join(emit(l0_tree))
