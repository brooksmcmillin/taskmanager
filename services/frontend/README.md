# TaskManager Frontend (SvelteKit)

Modern frontend for TaskManager built with SvelteKit and TypeScript.

## Stack

- **SvelteKit 2.0** - Application framework
- **Svelte 5** - Reactive UI with runes
- **TypeScript** - Type safety
- **SCSS** - Styling with design system
- **svelte-dnd-action** - Drag and drop calendar

## Development

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview

# Type checking
npm run check

# Format code
npm run format

# Run E2E tests
npm test
```

## Project Structure

```
src/
├── routes/              # SvelteKit file-based routing
│   ├── +layout.svelte   # Root layout with navigation
│   ├── +page.svelte     # Home dashboard (tasks + news feed)
│   ├── admin/           # Admin panel (loki logs, registration codes, relay)
│   ├── api-keys/        # API key management
│   ├── login/           # Login page
│   ├── news/            # News feed (articles, sources)
│   ├── notifications/   # Notification inbox
│   ├── oauth/           # OAuth flows (authorize, device)
│   ├── oauth-clients/   # OAuth client management
│   ├── privacy/         # Privacy policy
│   ├── projects/        # Project list and detail views
│   ├── recurring-tasks/ # Recurring task templates
│   ├── register/        # User registration
│   ├── settings/        # User and app settings (including passkeys)
│   ├── snippets/        # Text snippet library
│   ├── task/            # Task detail and new task views
│   ├── tasks/           # Task list with calendar view
│   ├── terms/           # Terms of service
│   ├── text-optin/      # Text/SMS opt-in
│   ├── trash/           # Deleted task recovery
│   └── wiki/            # Wiki pages (tree, editor, revisions)
├── lib/
│   ├── components/      # Svelte components
│   ├── stores/          # State management
│   ├── api/             # API client
│   ├── utils/           # Utility functions
│   └── types.ts         # TypeScript types
└── app.scss             # Global styles
```

## Key Components

- **DragDropCalendar** - Calendar view with drag-and-drop task scheduling
- **TaskDetailPanel** - Side panel for viewing and editing task details
- **WikiTreeView** - Hierarchical wiki page navigation
- **SearchModal** - Global search across tasks, wiki, snippets
- **Navigation** - App-wide navigation with connection status
- **ThemeToggle** - Light/dark mode toggle

## State Management (Svelte Stores)

- `todos` - Task list, filtering, CRUD operations
- `projects` - Project list and selection
- `wiki` - Wiki page tree and content
- `snippets` - Text snippet library
- `recurringTasks` - Recurring task templates
- `ui` - Toast notifications, modal state

## Environment Variables

Copy `.env.example` to `.env`:

```env
VITE_API_URL=http://localhost:8000
PUBLIC_APP_NAME=TaskManager
```

## Docker

```bash
# Build image
docker build -t taskmanager-frontend .

# Run container
docker run -p 3000:3000 taskmanager-frontend
```

## API Integration

The frontend connects to the FastAPI backend at `VITE_API_URL`. All API calls use cookie-based session authentication.

Example:

```typescript
import { api } from '$lib/api/client';

// Get todos
const response = await api.get<ApiResponse<Todo[]>>('/api/todos');

// Create todo
const todo = await api.post<Todo>('/api/todos', { title: 'New task' });
```

## Features

- Authentication (login, register, session management)
- Passkey/WebAuthn support for passwordless login
- Task management (list, calendar drag-and-drop, detail panel)
- Subtasks and task dependencies
- Project organization with filtering
- Recurring task templates
- Wiki with hierarchical pages, revisions, and task linking
- News feed with RSS/Atom sources and AI summaries
- Text snippets library with categories
- Notifications inbox
- OAuth 2.0 client management
- API key management
- Admin panel (Loki logs, registration codes, relay)
- Trash/restore for deleted tasks
- Global search across tasks, wiki, and snippets
- Light/dark theme toggle
- Responsive design with SCSS
