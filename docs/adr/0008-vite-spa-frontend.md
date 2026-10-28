# 0008. Vite single-page app instead of a server-rendered framework

- Status: accepted
- Date: 2026-10-28
- Related: FR-60–FR-62, ADR 0004, ADR 0005

## Context

The UI is a local tool: chat, document library, model selector, push-to-talk. No SEO, no public pages, one user. It must be served offline, ideally as static files.

## Decision

React with TypeScript, built with Vite into static assets, served by a small static server container (or by the API in development via the Vite proxy). Data fetching with TanStack Query over the generated client (ADR 0005). Routing with React Router. Styling with Tailwind CSS. No component library beyond small headless primitives where needed.

## Alternatives considered

- **Next.js** – server rendering, server actions and its own server add a second backend and a Node runtime for no user-facing benefit here.
- **A component library (MUI, Ant)** – larger bundle and more styling to override; the UI is small.

## Consequences

- Good: the frontend is a folder of static files, trivial to ship offline.
- Good: one backend, one place for business logic.
- Bad: none significant at this scope.
