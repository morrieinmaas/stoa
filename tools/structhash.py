# SPDX-License-Identifier: Apache-2.0
"""Encoding independence.

The structural hash is defined over the typed tree, never over a byte
serialisation. This program is the proof: it encodes the same document as
canonical JSON and as deterministic CBOR, decodes both back, and asserts one
digest and one set of Merkle leaves.

If this holds, the encoding is a revisable transport detail rather than part
of the format, and the signature claim does not depend on choosing JSON.

    python3 tools/structhash.py conformance/conformance-01.json
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stoa  # noqa: E402


# --------------------------------------------------------------------------
# deterministic CBOR, RFC 8949 section 4.2.1
#   definite lengths, shortest-form integers, map keys sorted by encoded bytes
# --------------------------------------------------------------------------

def _head(major, n):
    if n < 24:
        return bytes([major << 5 | n])
    for extra, tag in ((1, 24), (2, 25), (4, 26), (8, 27)):
        if n < 1 << (8 * extra):
            return bytes([major << 5 | tag]) + n.to_bytes(extra, "big")
    raise ValueError("value too large for CBOR")


def cbor_encode(v):
    if isinstance(v, bool):
        return bytes([0xF5 if v else 0xF4])
    if v is None:
        return b"\xf6"
    if isinstance(v, int):
        return _head(0, v) if v >= 0 else _head(1, -v - 1)
    if isinstance(v, str):
        b = stoa.nfc(v).encode("utf-8")
        return _head(3, len(b)) + b
    if isinstance(v, list):
        return _head(4, len(v)) + b"".join(cbor_encode(x) for x in v)
    if isinstance(v, dict):
        items = sorted(((cbor_encode(k), cbor_encode(x)) for k, x in v.items()),
                       key=lambda p: p[0])
        return _head(5, len(items)) + b"".join(k + x for k, x in items)
    if isinstance(v, stoa.Float):
        raise ValueError("floating point is unrepresentable in Stoa")
    raise ValueError(f"unencodable: {v!r}")


def cbor_decode(b, i=0):
    ib = b[i]
    major, minor = ib >> 5, ib & 0x1F
    i += 1
    if minor < 24:
        n = minor
    elif minor == 24:
        n, i = b[i], i + 1
    elif minor in (25, 26, 27):
        width = {25: 2, 26: 4, 27: 8}[minor]
        n, i = int.from_bytes(b[i:i + width], "big"), i + width
    elif ib in (0xF4, 0xF5):
        return ib == 0xF5, i
    elif ib == 0xF6:
        return None, i
    else:
        raise ValueError(f"unsupported CBOR head {ib:#x}")

    if major == 0:
        return n, i
    if major == 1:
        return -n - 1, i
    if major == 3:
        return b[i:i + n].decode("utf-8"), i + n
    if major == 4:
        out = []
        for _ in range(n):
            v, i = cbor_decode(b, i)
            out.append(v)
        return out, i
    if major == 5:
        out = {}
        for _ in range(n):
            k, i = cbor_decode(b, i)
            v, i = cbor_decode(b, i)
            out[k] = v
        return out, i
    if major == 7:
        return {20: False, 21: True, 22: None}[n], i
    raise ValueError(f"unsupported CBOR major type {major}")


# --------------------------------------------------------------------------

def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    reg = stoa.Register()
    doc = stoa.load_document(argv[1])

    json_bytes = stoa.canonical_json(doc)
    cbor_bytes = cbor_encode(stoa.nfc_tree(doc))

    from_json = stoa.load_json_bytes(json_bytes)
    from_cbor, end = cbor_decode(cbor_bytes)
    assert end == len(cbor_bytes), "trailing bytes after CBOR document"

    d_json = stoa.digest_hex(from_json)
    d_cbor = stoa.digest_hex(from_cbor)

    lj = [h.hex() for h in map(stoa.structural_hash, stoa.block_nodes(from_json, reg))]
    lc = [h.hex() for h in map(stoa.structural_hash, stoa.block_nodes(from_cbor, reg))]
    rj, _ = stoa.merkle([bytes.fromhex(h) for h in lj])
    rc, _ = stoa.merkle([bytes.fromhex(h) for h in lc])

    print(f"canonical JSON      {len(json_bytes):>6} bytes")
    print(f"deterministic CBOR  {len(cbor_bytes):>6} bytes "
          f"({100 * len(cbor_bytes) // len(json_bytes)}% of JSON)")
    print(f"digest from JSON    {d_json}")
    print(f"digest from CBOR    {d_cbor}")
    print(f"merkle from JSON    {rj.hex()}")
    print(f"merkle from CBOR    {rc.hex()}")
    print(f"block leaves        {len(lj)} identical: {lj == lc}")

    ok = (d_json == d_cbor) and (rj == rc) and (lj == lc)
    print(f"ENCODING INDEPENDENT {ok}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
