# Frontend Code Walkthrough

Everything inside the `frontend/` folder explained.

---

## How It's Built

```
React 18         ← UI component library
Vite             ← Dev server + build tool (much faster than Create React App)
TypeScript       ← Typed JavaScript (catches bugs before runtime)
Tailwind CSS     ← Styling via utility classes
React Router v6  ← Client-side navigation between pages
Zustand          ← Global state management (auth, current user)
Axios            ← HTTP requests to the backend
Lucide React     ← Icon library
```

---

## File Structure

```
frontend/
├── Dockerfile            ← How to containerise the frontend
├── package.json          ← Dependencies + npm scripts
├── vite.config.ts        ← Vite settings (dev server, API proxy)
├── tailwind.config.js    ← Tailwind theme (colors, fonts)
├── postcss.config.js     ← Required by Tailwind (do not remove)
├── tsconfig.json         ← TypeScript settings
├── index.html            ← The single HTML page (React mounts here)
└── src/
    ├── index.css         ← Global styles + Tailwind directives
    ├── main.tsx          ← React app bootstrap
    ├── App.tsx           ← Root component (currently: landing page)
    │
    ├── api/              [COMING NEXT]
    │   └── client.ts     ← Axios instance with JWT interceptor
    │
    ├── store/            [COMING NEXT]
    │   └── authStore.ts  ← Zustand store for login state
    │
    ├── components/       [COMING NEXT]
    │   ├── layout/
    │   │   ├── Sidebar.tsx        ← Left navigation
    │   │   ├── Header.tsx         ← Top bar with user info
    │   │   └── SecurityBanner.tsx ← Encryption status indicator
    │   └── ui/
    │       ├── Badge.tsx   ← Coloured status badges
    │       ├── Modal.tsx   ← Reusable dialog
    │       └── Spinner.tsx ← Loading indicator
    │
    └── pages/
        ├── Login.tsx          ← Secure auth with identity verification
        ├── Dashboard.tsx      ← Summary of system status and activity
        ├── Patients.tsx       ← Patient registry and lookup (Admin only)
        ├── PatientDetail.tsx  ← Deep dive into one patient (records, history)
        ├── Records.tsx        ← Central hub for medical record management
        ├── Timeline.tsx       ← Patient-centric unified medical timeline
        ├── EncryptionLab.tsx  ← Live cryptographic tool (demo)
        ├── AuditTrail.tsx     ← Immutable SHA-256 action logs (Admin)
        ├── UserManagement.tsx ← Role and attribute management (Admin)
        ├── Exchange.tsx       ← Inter-hospital data requests
        └── Settings.tsx       ← Account and system settings
```

---

## Key Config Files Explained

### `vite.config.ts` — The Dev Server

```typescript
proxy: {
  '/api': {
    target: 'http://backend:8000',
    changeOrigin: true,
    rewrite: (path) => path.replace(/^\/api/, ''),
  }
}
```

**What this does:** When the React app calls `/api/patients`, Vite rewrites it to `http://backend:8000/patients` and forwards it.

**Why:** The browser sees `localhost:5173` for both the frontend and API calls, so there's no CORS issue during development.

**In production:** You'd configure Nginx or a cloud load balancer to do the same routing.

---

### `tailwind.config.js` — Design Tokens

```javascript
colors: {
  brand: {
    50:  '#eef2ff',   // very light indigo
    500: '#6366f1',   // primary button color
    900: '#1e1b4b',   // dark backgrounds
  }
}
```

Use `text-brand-500`, `bg-brand-900` etc. in your components.
Never hardcode hex colours — use these tokens so the whole app is consistent.

---

### `src/index.css` — Global Styles

```css
@tailwind base;       ← Tailwind's CSS reset
@tailwind components; ← Tailwind's component styles
@tailwind utilities;  ← All the utility classes (text-sm, flex, etc.)

/* Inter font from Google Fonts */
@import url('https://fonts.googleapis.com/...');

body {
  @apply bg-gray-950 text-gray-100 font-sans antialiased;
}
```

The dark background (`bg-gray-950`) and light text (`text-gray-100`) establish the base dark theme.

---

## How React Bootstraps (`main.tsx`)

```
index.html
  └── <div id="root"></div>
  └── <script src="/src/main.tsx">

main.tsx
  └── createRoot(document.getElementById('root'))
  └── .render(<StrictMode><App /></StrictMode>)
```

`StrictMode` makes React run extra checks during development and warn about outdated patterns. It doesn't affect production builds.

---

## Planned App Flow (Phase 2+)

```
App.tsx
└── <Router>
    ├── /login             → Login.tsx (public)
    └── <ProtectedLayout>  (requires valid JWT session)
        ├── /dashboard     → Dashboard.tsx
        ├── /patients      → Patients.tsx
        ├── /patients/:id  → PatientDetail.tsx
        ├── /records       → Records.tsx
        ├── /timeline      → Timeline.tsx (Unified medical file)
        ├── /audit         → AuditTrail.tsx (Admin only)
        ├── /exchange      → Exchange.tsx
        ├── /encryption    → EncryptionLab.tsx
        ├── /users         → UserManagement.tsx (Admin only)
        └── /settings      → Settings.tsx
```

`ProtectedLayout` will check the Zustand store — if no token, redirect to `/login`.

---

## State Management (Zustand — coming next)

```typescript
// src/store/authStore.ts (planned)
interface AuthStore {
  token: string | null
  user: { id: string; role: string; name: string } | null
  login: (token: string, user: User) => void
  logout: () => void
}
```

Why Zustand over Redux?
- No action creators, no reducers, no boilerplate
- Just a store object with functions
- Works perfectly for this scale of app

---

## API Client (Axios — coming next)

```typescript
// src/api/client.ts (planned)
const api = axios.create({ baseURL: '/api' })

// Automatically attach JWT to every request
api.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Redirect to login on 401
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)
```

Every page imports from `api/client.ts` — never from Axios directly.
This way JWT injection and 401 handling happen in one place.

---

## Styling Convention

Use Tailwind utilities directly in JSX:

```tsx
// Good ✓
<button className="px-4 py-2 bg-brand-600 hover:bg-brand-500 rounded-lg text-white">
  Submit
</button>

// Avoid ✗ (no separate CSS files for components)
<button className={styles.submitButton}>Submit</button>
```

For repeated patterns, extract a component — not a CSS class.
