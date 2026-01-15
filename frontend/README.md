# TaskManager Frontend (SvelteKit)

Modern frontend for TaskManager built with SvelteKit and TypeScript.

## Stack

- **SvelteKit 2.0** - Application framework
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
```

## Project Structure

```
src/
├── routes/              # SvelteKit file-based routing
│   ├── +layout.svelte   # Root layout
│   ├── +page.svelte     # Dashboard (index)
│   ├── login/
│   ├── register/
│   ├── projects/
│   └── oauth-clients/
├── lib/
│   ├── components/      # Svelte components
│   ├── stores/          # State management
│   ├── api/             # API client
│   ├── utils/           # Utility functions
│   └── types.ts         # TypeScript types
└── app.scss             # Global styles
```

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

## Migration Status

- [x] Phase 2.1: SvelteKit Project Setup
- [x] Phase 2.2: SCSS Styles Ported
- [ ] Phase 2.3: Authentication Pages
- [ ] Phase 2.4: Task Management UI
- [ ] Phase 2.5: Calendar Component
- [ ] Phase 2.6: OAuth Client Management
