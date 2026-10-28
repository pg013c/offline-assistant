# General standards

## Structure

- **GEN-01** One reason to change per module. If a file's description needs "and", split it.
- **GEN-02** Depend on abstractions at boundaries (ports), on concrete code inside a layer. No abstraction without a second implementation or a test fake that needs it.
- **GEN-03** Dependencies are passed in (constructor or function argument). No module-level singletons, no hidden global state, no service locators.
- **GEN-04** Pure functions for logic, side effects at the edges. A function either computes or performs I/O, not both, where practical.
- **GEN-05** No dead code, commented-out code or speculative options. Delete; git remembers.

## Naming and readability

- **GEN-10** Names say what something is in the domain language of the PRD: `Chunk`, `Citation`, `refusal`, not `data`, `item`, `result2`.
- **GEN-11** Functions are verbs, booleans read as questions (`is_refusal`, `has_citations`).
- **GEN-12** Comments explain why, never what. A comment that restates the code is removed.
- **GEN-13** Everything in English: code, comments, docs, commit messages, UI copy (the UI may additionally be localised).

## Errors

- **GEN-20** Fail loudly and early on invalid input or missing configuration. No silent defaults for required settings.
- **GEN-21** Errors carry context: what was attempted, with which identifiers. Never swallow an exception without logging and re-raising or converting it.
- **GEN-22** Expected failures (no results, model refused, invalid model output after retries) are values in the domain, not exceptions.

## Dependencies

- **GEN-30** A new runtime dependency needs an ADR (or a line in an existing one) with its licence. Dev-only tools need a one-line reason in the PR.
- **GEN-31** Versions are locked (`uv.lock`, `pnpm-lock.yaml`). Models are pinned by exact version or file hash in configuration.

## Security and privacy

- **GEN-40** No secrets in the repository. Configuration from environment variables with a committed `.env.example`.
- **GEN-41** User documents, notes and logs never leave the machine (ADR 0004). Logs do not contain full document text or full prompts at info level.
- **GEN-42** All file paths from users are validated against the storage root (no path traversal). Uploads are size- and type-limited.

## Configuration

- **GEN-50** One settings object per project, typed and validated at startup. No `os.environ` / `import.meta.env` reads outside it.
