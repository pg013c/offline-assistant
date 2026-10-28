# Frontend standards

Applies to `frontend/`. Enforced by `make check` in `frontend/`.

## Toolchain

- **FE-01** React 19, TypeScript in `strict` mode with `noUncheckedIndexedAccess`, Vite, pnpm. Node version pinned in `.nvmrc`.
- **FE-02** ESLint (typescript-eslint strict, react-hooks, jsx-a11y) and Prettier. Zero warnings. `tsc --noEmit` passes.
- **FE-03** No `any`. `unknown` plus narrowing at boundaries. No non-null assertions (`!`) except in tests.

## Data and API

- **FE-10** The backend is called only through the generated client in `src/api/` (ADR 0005). No hand-written `fetch` to the API, no duplicated API types.
- **FE-11** Server state lives in TanStack Query. Local UI state in `useState`/`useReducer`. No global store until a feature proves the need (ADR).
- **FE-12** SSE streams are consumed in one hook per stream type (e.g. `useChatStream`), which exposes typed events and handles reconnection and cancellation.

## Components

- **FE-20** Feature folders: `src/features/<feature>/` holds its components, hooks and tests. Shared, feature-agnostic UI goes in `src/components/`.
- **FE-21** Components render; hooks hold logic. A component with non-trivial logic gets a hook that is tested on its own.
- **FE-22** Props are typed with explicit interfaces. No prop drilling more than two levels; lift to a hook or context scoped to the feature.
- **FE-23** No `useEffect` for derived state or data fetching. Effects only for synchronising with external systems (audio, media devices, event sources).
- **FE-24** Accessible by default: semantic elements, labels on every control, keyboard operation of chat, push-to-talk and citation links.
- **FE-25** Styling with Tailwind utility classes. No inline style objects except for dynamic values.

## Layout

```text
frontend/
├── src/
│   ├── api/              generated client and schema (committed, not edited)
│   ├── features/
│   │   ├── chat/
│   │   ├── documents/
│   │   └── voice/
│   ├── components/
│   └── main.tsx
└── e2e/                  Playwright journeys
```
