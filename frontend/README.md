# DocuMind — Frontend

React 18 + TypeScript + Vite + Tailwind single-page app for the DocuMind AI Document Intelligence & Hybrid RAG system.
It talks to the FastAPI backend exclusively through relative `/api` calls, as specified in [`../docs/API.md`](../docs/API.md).

## Commands

```bash
npm install        # install dependencies
npm run dev        # dev server on http://localhost:5173 (proxies /api -> http://localhost:8000)
npm run build      # type-check (tsc --noEmit) + production build into ./dist
npm run preview    # serve the built ./dist locally
npm run typecheck  # type-check only
```

The backend serves `frontend/dist` at `/` with SPA fallback, so after `npm run build` the whole app is available at
http://localhost:8000.
1
## Structure

```
src/
  App.tsx            routes (lazy-loaded pages, protected routes)
  main.tsx           providers: router, react-query, theme, auth
  types.ts           TypeScript types mirroring docs/API.md
  lib/api.ts         fetch wrapper (Bearer token, 401 -> login), SSE streaming, XHR upload with progress
  lib/utils.ts       formatting helpers
  hooks/             auth + theme contexts, react-query hooks, misc hooks
  components/ui/     hand-rolled primitives (Button, Card, Badge, Input, Dialog, Drawer, Tabs, Tooltip/Popover, Skeleton, EmptyState…)
  components/        layout (sidebar, top bar, Ctrl+K palette), chat, documents, charts, system status
  pages/             Auth, Dashboard, Documents, Chat, Insights, Evaluation, Settings, 404
```

Theme (dark default) and sidebar state are persisted in `localStorage`; the auth token is stored under `documind-token`.
