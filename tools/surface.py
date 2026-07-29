# SPDX-License-Identifier: Apache-2.0
"""M0c: a surface syntax, and the fixed-point test that keeps it honest.

The tree is the document. A surface is an *input language*, it is non-normative,
and there can be many -- design notes section 8. That claim is cheap to make and
expensive to be wrong about, because a lossy surface silently destroys authored
content the first time a document round-trips through any tool.

So the surface ships with the test rather than the promise. Two directions:

    tree -> text -> tree     the structural digest must be unchanged
    text -> tree -> text     the bytes must be unchanged

The first is the one that matters: it says the surface can express every
element in the register without losing a field, a child, or an order. The
second says the emitter and parser agree, which is what makes a surface usable
in a diff and a review.

The syntax is contained by CommonMark wherever CommonMark has a construct with
the same meaning, so existing editors, diff tools and review workflows work on
day one. Everything else uses two generic extensions, which is what keeps the
surface total rather than approximate:

    ::: element key=value          a block, closed by :::
    {{element key=value}}          an inline with no children
    {{element key=value}}x{{/}}    an inline with children

    python3 tools/surface.py conformance/conformance-01.json fixedpoint
    python3 tools/surface.py conformance/conformance-01.json emit
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa  # noqa: E402

REG = stoa.Register()

# CommonMark constructs that mean the same thing as a register element.
NATIVE_BLOCK = {"heading", "paragraph", "list", "item", "quote", "code-block",
                "term-list", "term", "definition"}
NATIVE_INLINE = {"text", "emphasis", "strong", "code", "link"}


# --------------------------------------------------------------------------
# attributes
# --------------------------------------------------------------------------

def fmt_attrs(node):
    out = []
    for k in sorted(stoa.fields(node)):
        v = node[k]
        if isinstance(v, bool):
            s = "true" if v else "false"
        elif isinstance(v, int):
            s = str(v)
        else:
            s = str(v)
            if re.search(r'[\s"=}:]', s) or s == "":
                s = '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
        out.append(f"{k}={s}")
    return (" " + " ".join(out)) if out else ""


ATTR = re.compile(r'([A-Za-z_][A-Za-z0-9_-]*)=("(?:[^"\\]|\\.)*"|[^\s}]*)')


def parse_attrs(name, text):
    """Coerce using the register, so the surface never has to encode types."""
    spec = REG[name].get("fields", {}) if name in REG else {}
    out = {}
    for k, raw in ATTR.findall(text or ""):
        if raw.startswith('"'):
            v = raw[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        else:
            v = raw
        t = spec.get(k, {}).get("type")
        if t == "int":
            try:
                v = int(v)
            except ValueError:
                pass
        elif t == "bool":
            v = v == "true"
        out[k] = v
    return out


# --------------------------------------------------------------------------
# inline
# --------------------------------------------------------------------------

ESCAPES = ("\\", "*", "_", "`", "[", "]", "{", "}", "#", ">", "|", ":")


def esc(s):
    for c in ESCAPES:
        s = s.replace(c, "\\" + c)
    return s


def unesc(s):
    return re.sub(r"\\(.)", r"\1", s)


def emit_inline(nodes):
    out = []
    for n in nodes:
        name = stoa.typ(n)
        kids = stoa.children(n)
        if name == "text":
            out.append(esc(str(n.get("v", ""))))
        elif name == "emphasis":
            out.append("*" + emit_inline(kids) + "*")
        elif name == "strong":
            out.append("**" + emit_inline(kids) + "**")
        elif name == "code":
            out.append("`" + "".join(str(c.get("v", "")) for c in kids) + "`")
        elif name == "link":
            out.append("[" + emit_inline(kids) + "](" + n.get("href", "") + ")")
        elif kids:
            out.append("{{" + name + fmt_attrs(n) + "}}"
                       + emit_inline(kids) + "{{/}}")
        else:
            out.append("{{" + name + fmt_attrs(n) + "}}")
    return "".join(out)


TOKEN = re.compile(
    r"(?P<esc>\\.)"
    r"|(?P<extopen>\{\{\s*(?P<xname>[a-z-]+)(?P<xattrs>[^}]*)\}\})"
    r"|(?P<extclose>\{\{/\}\})"
    r"|(?P<strong>\*\*)"
    r"|(?P<em>\*)"
    r"|(?P<code>`(?P<codetext>(?:[^`\\]|\\.)*)`)"
    r"|(?P<link>\[)"
)


def parse_inline(s):
    nodes, buf, i = [], [], 0
    stack = []

    def flush():
        # an empty run is absence of text, not a text node carrying nothing --
        # the same rule the degradation projection had to learn
        v = unesc("".join(buf))
        buf.clear()
        if v:
            (stack[-1]["c"] if stack else nodes).append({"t": "text", "v": v})

    def push(node):
        (stack[-1]["c"] if stack else nodes).append(node)

    while i < len(s):
        m = TOKEN.search(s, i)
        if not m:
            buf.append(s[i:])
            break
        buf.append(s[i:m.start()])
        i = m.end()
        if m.group("esc"):
            buf.append(m.group("esc"))
        elif m.group("extopen"):
            flush()
            name = m.group("xname")
            node = {"t": name}
            node.update(parse_attrs(name, m.group("xattrs")))
            # a wrapping extension is closed by {{/}}; a void one is not
            nxt = s.find("{{/}}", i)
            takes_kids = name in REG and REG[name].get("children") not in ("none",)
            if takes_kids and nxt != -1:
                node["c"] = []
                push(node)
                stack.append(node)
            else:
                push(node)
        elif m.group("extclose"):
            flush()
            if stack:
                stack.pop()
        elif m.group("strong"):
            flush()
            if stack and stack[-1].get("t") == "strong":
                stack.pop()
            else:
                n = {"t": "strong", "c": []}
                push(n)
                stack.append(n)
        elif m.group("em"):
            flush()
            if stack and stack[-1].get("t") == "emphasis":
                stack.pop()
            else:
                n = {"t": "emphasis", "c": []}
                push(n)
                stack.append(n)
        elif m.group("code"):
            flush()
            push({"t": "code", "c": [{"t": "text", "v": unesc(m.group("codetext"))}]})
        elif m.group("link"):
            flush()
            depth, j = 1, i
            while j < len(s) and depth:
                if s[j] == "\\":
                    j += 2
                    continue
                if s[j] == "[":
                    depth += 1
                elif s[j] == "]":
                    depth -= 1
                j += 1
            label, rest = s[i:j - 1], s[j:]
            mm = re.match(r"\((?P<href>[^)]*)\)", rest)
            if mm:
                push({"t": "link", "href": mm.group("href"),
                      "c": parse_inline(label)})
                i = j + mm.end()
            else:
                buf.append("[")
        else:
            buf.append(m.group(0))
    flush()
    return nodes


# --------------------------------------------------------------------------
# blocks
# --------------------------------------------------------------------------

def emit_blocks(nodes, out, indent=""):
    for n in nodes:
        name = stoa.typ(n)
        kids = stoa.children(n)
        if name == "heading":
            out.append(indent + "#" * n.get("level", 1) + " " + emit_inline(kids))
            out.append("")
        elif name == "paragraph":
            out.append(indent + emit_inline(kids))
            out.append("")
        elif name == "list":
            for k, it in enumerate(kids, start=n.get("start", 1)):
                mark = f"{k}. " if n.get("ordered") else "- "
                sub = []
                emit_blocks(stoa.children(it), sub, indent + "  ")
                sub = [x for x in sub if x.strip()]
                if sub:
                    out.append(indent + mark + sub[0].lstrip())
                    out.extend(sub[1:])
            out.append("")
        elif name == "term-list":
            for c in kids:
                if stoa.typ(c) == "term":
                    out.append(indent + emit_inline(stoa.children(c)))
                else:
                    sub = []
                    emit_blocks(stoa.children(c), sub, indent)
                    for x in [y for y in sub if y.strip()]:
                        out.append(indent + ": " + x.lstrip())
            out.append("")
        elif name == "quote":
            sub = []
            emit_blocks(kids, sub, "")
            for x in [y for y in sub if y.strip()]:
                out.append(indent + "> " + x)
            if n.get("source"):
                out.append(indent + "> {{source " + fmt_attrs(
                    {"v": n["source"]}).strip() + "}}")
            out.append("")
        elif name == "code-block":
            out.append(indent + "```" + (n.get("language") or ""))
            for c in kids:
                out.extend(indent + line for line in
                           str(c.get("v", "")).split("\n"))
            out.append(indent + "```")
            out.append("")
        else:
            out.append(indent + "::: " + name + fmt_attrs(n))
            if kids and all(stoa.typ(k) == "item" for k in kids):
                emit_blocks([{"t": "list", "ordered": False, "c": kids}],
                            out, indent)
            elif kids:
                emit_blocks(kids, out, indent)
            while out and not out[-1].strip():
                out.pop()
            out.append(indent + ":::")
            out.append("")
    return out


def emit(doc):
    out = ["---"]
    for k in sorted(stoa.fields(doc)):
        out.append(f"{k}: {doc[k]}")
    out.append("---")
    out.append("")
    emit_blocks(stoa.children(doc), out)
    return "\n".join(out).rstrip() + "\n"


def dedent(lines, n):
    return [l[n:] if len(l) >= n and l[:n].strip() == "" else l.lstrip()
            for l in lines]


def parse_blocks(lines):
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        stripped = line.lstrip()
        ind = len(line) - len(stripped)

        if stripped.startswith("::: "):
            m = re.match(r"::: ([a-z-]+)(.*)$", stripped)
            name = m.group(1)
            node = {"t": name}
            node.update(parse_attrs(name, m.group(2)))
            depth, j, body = 1, i + 1, []
            while j < len(lines):
                t = lines[j].strip()
                if t.startswith("::: "):
                    depth += 1
                elif t == ":::":
                    depth -= 1
                    if depth == 0:
                        break
                body.append(lines[j])
                j += 1
            kids = parse_blocks(dedent(body, ind))
            model = REG[name].get("children") if name in REG else None
            if (isinstance(model, list) and "item" in model
                    and len(kids) == 1 and stoa.typ(kids[0]) == "list"):
                kids = stoa.children(kids[0])
            if kids:
                node["c"] = kids
            out.append(node)
            i = j + 1
        elif stripped.startswith("```"):
            lang = stripped[3:].strip()
            j, body = i + 1, []
            while j < len(lines) and lines[j].strip() != "```":
                body.append(lines[j][ind:] if len(lines[j]) >= ind else lines[j])
                j += 1
            node = {"t": "code-block", "c": [{"t": "text", "v": "\n".join(body)}]}
            if lang:
                node["language"] = lang
            out.append(node)
            i = j + 1
        elif re.match(r"#{1,6} ", stripped):
            h, rest = stripped.split(" ", 1)
            out.append({"t": "heading", "level": len(h),
                        "c": parse_inline(rest)})
            i += 1
        elif stripped.startswith("> "):
            body, j = [], i
            src = None
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                t = lines[j].lstrip()[1:]
                t = t[1:] if t.startswith(" ") else t
                m = re.match(r"\{\{source (.*)\}\}$", t.strip())
                if m:
                    src = parse_attrs("__src", m.group(1)).get("v", "")
                else:
                    body.append(t)
                j += 1
            node = {"t": "quote", "c": parse_blocks(body)}
            if src:
                node["source"] = src
            out.append(node)
            i = j
        elif re.match(r"(- |\d+\. )", stripped):
            ordered = not stripped.startswith("- ")
            items, j = [], i
            start = None
            while j < len(lines):
                s2 = lines[j].lstrip()
                m = re.match(r"(?:- |(\d+)\. )", s2)
                if not m or (len(lines[j]) - len(s2)) != ind:
                    if lines[j].strip() and (len(lines[j]) - len(s2)) > ind:
                        items[-1].append(lines[j])
                        j += 1
                        continue
                    if not lines[j].strip():
                        j += 1
                        continue
                    break
                if start is None and m.group(1):
                    start = int(m.group(1))
                items.append([" " * (ind + 2) + s2[m.end():]])
                j += 1
            node = {"t": "list", "ordered": ordered,
                    "c": [{"t": "item", "c": parse_blocks(dedent(b, ind + 2))}
                          for b in items]}
            if ordered and start not in (None, 1):
                node["start"] = start
            out.append(node)
            i = j
        elif i + 1 < len(lines) and lines[i + 1].lstrip().startswith(": "):
            pairs, j = [], i
            while j < len(lines):
                s2 = lines[j].lstrip()
                if not s2 or s2.startswith(": "):
                    break
                pairs.append({"t": "term", "c": parse_inline(s2)})
                j += 1
                defs = []
                while j < len(lines) and lines[j].lstrip().startswith(": "):
                    defs.append(lines[j].lstrip()[2:])
                    j += 1
                pairs.append({"t": "definition", "c": parse_blocks(defs)})
            out.append({"t": "term-list", "c": pairs})
            i = j
        else:
            out.append({"t": "paragraph", "c": parse_inline(stripped)})
            i += 1
    return out


def parse(text):
    lines = text.split("\n")
    doc = {"t": "document"}
    if lines and lines[0].strip() == "---":
        j = 1
        while j < len(lines) and lines[j].strip() != "---":
            k, _, v = lines[j].partition(":")
            doc[k.strip()] = v.strip()
            j += 1
        lines = lines[j + 1:]
    kids = parse_blocks(lines)
    if kids:
        doc["c"] = kids
    return doc


# --------------------------------------------------------------------------

def fixedpoint(doc):
    text = emit(doc)
    back = parse(text)
    again = emit(back)

    d1, d2 = stoa.digest_hex(doc), stoa.digest_hex(back)
    tree_ok = d1 == d2
    text_ok = text == again

    errs = [d for d in stoa.validate(back, REG) if d.sev == "error"]
    used = {stoa.typ(n) for n, _ in stoa.walk(doc) if stoa.typ(n) in REG}

    print(f"surface bytes       {len(text.encode()):>6}  "
          f"({100 * len(text.encode()) // len(stoa.canonical_json(doc))}% of canonical JSON)")
    print(f"elements exercised  {len(used)} of {len(REG.elements)}")
    print(f"digest from tree    {d1}")
    print(f"digest via surface  {d2}")
    print(f"TREE FIXED POINT    {tree_ok}   (tree -> text -> tree)")
    print(f"TEXT FIXED POINT    {text_ok}   (text -> tree -> text)")
    print(f"reparsed conforms   {not errs} ({len(errs)} errors)")
    for d in errs[:5]:
        print(f"   {d}")
    if not tree_ok:
        a = json.loads(stoa.canonical_json(doc))
        b = json.loads(stoa.canonical_json(back))
        diff(a, b, "")
    return 0 if (tree_ok and text_ok and not errs) else 1


def diff(a, b, path, n=[0]):
    if n[0] > 6:
        return
    if stoa.typ(a) != stoa.typ(b):
        print(f"   {path}: {stoa.typ(a)} != {stoa.typ(b)}")
        n[0] += 1
        return
    fa, fb = stoa.fields(a), stoa.fields(b)
    if fa != fb:
        print(f"   {path}/{stoa.typ(a)}: fields {fa} != {fb}")
        n[0] += 1
    ka, kb = stoa.children(a), stoa.children(b)
    if len(ka) != len(kb):
        print(f"   {path}/{stoa.typ(a)}: {len(ka)} children != {len(kb)} "
              f"({[stoa.typ(x) for x in ka]} vs {[stoa.typ(x) for x in kb]})")
        n[0] += 1
    for i, (x, y) in enumerate(zip(ka, kb)):
        diff(x, y, f"{path}/{stoa.typ(a)}[{i}]")


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    doc = stoa.load_document(argv[1])
    if argv[2] == "emit":
        sys.stdout.write(emit(doc))
        return 0
    if argv[2] == "fixedpoint":
        return fixedpoint(doc)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
