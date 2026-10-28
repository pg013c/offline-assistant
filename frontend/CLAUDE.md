# Frontend

React 19, TypeScript strict, Vite, pnpm, TanStack Query, Tailwind.

Rules: [../docs/standards/react.md](../docs/standards/react.md), [../docs/standards/testing.md](../docs/standards/testing.md).

- Call the backend only through the generated client in `src/api/`. After a backend API change, run `make api-client` and commit the result.
- Feature folders in `src/features/<feature>/`; components render, hooks hold logic and are tested on their own.
- Tests: Vitest + Testing Library next to the code (`*.test.tsx`); HTTP is mocked with the shared msw server in `src/test/`, which counts as test code (read-only in the green phase). Playwright journeys in `e2e/` arrive with F-01.
