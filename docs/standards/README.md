# Engineering standards

The rules every change follows, whoever writes it. The coding agent applies them while building; the `reviewer` agent checks against them; findings cite the rule id (e.g. `PY-04`).

| File | Ids | Covers |
|---|---|---|
| [general.md](general.md) | `GEN-` | All code: structure, naming, errors, dependencies, security |
| [python.md](python.md) | `PY-` | Backend |
| [react.md](react.md) | `FE-` | Frontend |
| [ai.md](ai.md) | `AI-` | Prompts, models, retrieval, tool calling, offline rules |
| [testing.md](testing.md) | `TEST-` | What is tested how, test style |

Rules are short and checkable. Where a tool can enforce a rule, the tool is named and the rule is enforced in `make check`; a rule nobody enforces is not written here.

Standards change only through an ADR.
