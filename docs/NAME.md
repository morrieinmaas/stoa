# On the name

**Current name:** Stoa. **Status:** provisional, and cheap to change.

## Why not the working name

The earlier working name was "Stratum." It collides directly with the Stratum mining protocol, which is widely known and well established in its own domain. That is not a collision worth fighting, and discovering it after publication is worse than changing it now.

## Why Stoa

A stoa is a public colonnade: a civic building assembled from a small vocabulary of standard, repeated elements, open to anyone, where public business was conducted and public notices were posted. That is the format described in one word.

Practical properties:

- Short, and pronounceable in English, Dutch, and Greek.
- Greek without being obscure, which fits both the first corpus and the general orientation of the work.
- Not obviously colliding in the protocol or format space.
- Does not describe a mechanism, so it does not become wrong when the mechanism changes.

## Before committing

- EUIPO search, classes 9 (software) and 42 (software development services).
- Domain and package-namespace availability.
- Check for existing use in the standards and archival space specifically, since that is where the format's own audience lives.

## How to change it

The name appears in prose, in crate names, in the media type (`application/prs.stoa`), in the well-known path (`/.well-known/stoa/theme/<hash>`), and in the document identifier URN. All of it is mechanical:

```sh
grep -rl "Stoa\|stoa" . | xargs sed -i 's/Stoa/NewName/g; s/stoa/newname/g'
```

Then regenerate the golden output, because the document identifier is part of the tree and therefore part of the hash:

```sh
python3 tools/newname0.py conformance/conformance-01.json l0 > conformance/expected/conformance-01.l0.txt
```

The media type is registered as `prs.` (personal tree) precisely so that renaming before standardisation costs nothing.
