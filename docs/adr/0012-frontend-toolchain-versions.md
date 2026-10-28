# 0012. Frontend toolchain versions

- Status: accepted
- Date: 2026-10-28
- Related: ADR 0011, FE-01, FE-02, F-00

## Context

ADR 0011 lists the frontend tooling and pins pnpm 11. Scaffolding the frontend with the current `create-vite` template showed three differences:

- The template uses TypeScript 7 (the native compiler). The latest typescript-eslint (8.72) supports TypeScript `>=4.8.4 <6.1.0`, so TypeScript 7 cannot be linted with type information yet.
- The template uses oxlint instead of ESLint. ADR 0011 chose ESLint for `jsx-a11y` (FE-02, FE-24).
- Corepack resolves pnpm 12, not 11.

## Decision

- **TypeScript 5.9**, pinned with `~5.9`. Moving to TypeScript 7 is a separate decision once typescript-eslint supports it.
- **ESLint** with typescript-eslint, react-hooks and jsx-a11y, as in ADR 0011; oxlint is not used.
- **pnpm 12**, pinned in `package.json` (`packageManager`) and used through Corepack. This replaces "pnpm 11" in ADR 0011.
- The template's development helpers stay: `@eslint/js` and `globals` (ESLint configuration), `eslint-plugin-react-refresh` (keeps hot reload correct), `@types/*` packages. All MIT.

## Alternatives considered

- **TypeScript 7 without type-aware lint rules** – faster type checking, but loses the strict typescript-eslint rules that FE-02 relies on.
- **TypeScript 6.0** – supported by typescript-eslint and newer than 5.9, but a transition release; 5.9 is the version the ecosystem has been tested against longest.
- **oxlint** – much faster, but without the accessibility rules we require.

## Consequences

- Good: the toolchain matches the standards, and every package has a recorded reason.
- Bad: we stay behind the newest TypeScript for a while. Revisit when typescript-eslint supports TypeScript 7.
