# ADR-0011 — Next.js + TypeScript + Tailwind + shadcn/ui frontend

## Status

Accepted.

## Context

`docs/02` and `docs/09` require React, Next.js, and TypeScript, a dark Jarvis-style HUD,
streaming chat, reusable panel components, and desktop-first responsiveness — while
warning against animation that hurts performance. The styling and data-fetching choices
were left open.

## Decision

* **Next.js 15 (App Router) + React 19 + TypeScript (strict).** Mandated by the docs;
  the App Router's server components also let the API bearer token stay server-side
  (ADR-0006).
* **Tailwind CSS v4** for styling. A HUD is mostly bespoke layout, glow, and borders;
  utility classes express that faster than a component library's theme system, and there
  is no design system to fight.
* **shadcn/ui (Radix primitives)** for behavioural components — dialogs, popovers,
  dropdowns, tabs. These are copied into the repo rather than installed as a dependency,
  so they can be restyled into the HUD aesthetic freely, and Radix gives keyboard and
  screen-reader behaviour we would otherwise implement badly.
* **TanStack Query** for REST state — caching, refetching, and optimistic updates for
  tasks/projects, which is a meaningful amount of code not to write.
* **Streaming via `fetch` + `ReadableStream`**, per ADR-0007.
* **Framer Motion**, used deliberately and sparingly: panel transitions and the agent
  activity indicator. `docs/09` explicitly warns against decoration.
* **Types generated from the backend's OpenAPI schema** into `frontend/lib/api-types.ts`,
  checked in CI. Frontend and backend cannot drift silently — a backend field rename
  becomes a frontend type error.
* **Tooling:** pnpm, ESLint, Prettier, Vitest for component logic, Playwright for a
  small number of smoke flows.

## Alternatives considered

* **Vite + React SPA.** Lighter and faster to build, but the docs specify Next.js, and
  server-side token handling and route handlers are genuinely useful here.
* **MUI / Chakra / Mantine.** Faster to assemble a conventional dashboard, but their
  visual identity is the opposite of a bespoke HUD and would be fought at every step.
* **Redux / Zustand for server state.** Unnecessary; server state belongs in TanStack
  Query and the little remaining client state fits in React context.

## Consequences

* Tailwind v4 is recent; some ecosystem plugins may lag. Acceptable — little is needed
  beyond core.
* Generated API types add a build step that must run whenever backend schemas change.
* The HUD aesthetic is hand-built, which is more design work than adopting a theme —
  but that is the point of the requirement.
