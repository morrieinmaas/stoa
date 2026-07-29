# Licensing

Three artifact classes, three licences, chosen so nothing here can ever require permission to implement. Rationale in `GOVERNANCE.md`.

| Path | Licence | SPDX |
|---|---|---|
| `design/`, `spec/`, `*.md` at the root | Creative Commons Attribution 4.0 International | `CC-BY-4.0` |
| `conformance/` | Creative Commons Zero 1.0 Universal | `CC0-1.0` |
| `tools/`, and all future implementation code | Apache License 2.0 | `Apache-2.0` |

Specification text is CC BY 4.0 so that independent implementations, derivative specifications, and translations are permitted irrevocably. Conformance fixtures are CC0 because test data carrying obligations is test data people route around. Implementation code is Apache-2.0 rather than MIT specifically for the explicit patent grant, which matters more for a format than for an application.

## Patent position

No patent claims are asserted over the format, the canonical encoding, the structural hash, or any conformant implementation, and none will be. Implementation is royalty-free and unconditional.

## Trademark

The name is the single reserved right. Anyone may fork, implement, extend, or compete; only conforming implementations may use the name. Without that, "conformant" means nothing and the accessibility and integrity claims become unenforceable. See `GOVERNANCE.md` section 2.

## TODO before publishing

Drop the full licence texts into `LICENSES/` following the REUSE specification:

```sh
mkdir -p LICENSES
# CC-BY-4.0.txt, CC0-1.0.txt, Apache-2.0.txt
# https://github.com/spdx/license-list-data/tree/main/text
```

Add SPDX headers to source files. `reuse lint` should pass before the first tagged release.
