# Frontend

React 19, TypeScript strict, Vite, pnpm, TanStack Query, Tailwind.

Rules: [../docs/standards/react.md](../docs/standards/react.md), [../docs/standards/testing.md](../docs/standards/testing.md).

- Call the backend only through the generated client in `src/api/`. After a backend API change, run `make api-client` and commit the result.
- Feature folders in `src/features/<feature>/`; components render, hooks hold logic and are tested on their own.
- Tests: Vitest + Testing Library next to the code (`*.test.tsx`), Playwright journeys in `e2e/` against a fake backend.

The project is scaffolded in F-00.
