# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

| Command           | Purpose                                    |
| ----------------- | ------------------------------------------ |
| `npm run dev`     | Start development server at localhost:4321 |
| `npm run build`   | Build production site to ./dist/           |
| `npm run preview` | Preview production build locally           |

## Architecture Overview

This is an Astro-based task management application with server-side rendering and API routes.

### Core Architecture

- **Frontend**: Astro with SSR enabled, custom CSS design system
- **Backend**: Astro API routes handling REST endpoints
- **Database**: SQLite with better-sqlite3, single file (`todos.db`)
- **Authentication**: Session-based auth with bcrypt password hashing
- **Middleware**: Route protection with Astro middleware
- **Styling**: Custom CSS design system in `/src/styles/global.css`

### Database Schema

The application uses SQLite with four main tables:

- `users`: User accounts with username, email, password hash
- `sessions`: User sessions with expiration tracking
- `projects`: Project management with name, description, color
- `todos`: Task items linked to projects with priority, status, time tracking

### Key Components Structure

- **Layout System**: `src/layouts/Layout.astro` includes global CSS and navigation
- **Navigation**: `src/components/Navigation.astro` - reusable nav with active states
- **Forms**: `src/components/TodoForm.astro` - handles todo creation with project selection
- **Auth Pages**: `src/pages/login.astro`, `src/pages/register.astro` - user authentication
- **Database Layer**: `src/lib/db.js` - TodoDB class with static methods for all database operations
- **Auth Layer**: `src/lib/auth.js` - Auth class for user management and session handling
- **Middleware**: `src/middleware.js` - route protection and user context

### API Architecture

RESTful API endpoints in `/src/pages/api/`:

- `/api/todos` - GET (with filters), POST, PUT for todo operations
- `/api/projects` - GET, POST for project management
- `/api/todos/[id]/complete` - POST for completing todos with time tracking
- `/api/auth/login` - POST for user authentication
- `/api/auth/register` - POST for user registration
- `/api/auth/logout` - POST for session termination
- `/api/auth/me` - GET for current user info

### CSS Design System

Custom design system with CSS variables and utility classes:

- Component classes: `.card`, `.btn`, `.form-input`, `.nav-link`
- Utility classes for layout, spacing, typography
- Responsive design with container and grid utilities

### Data Flow

1. User authentication through login/register forms
2. Middleware protects routes and provides user context
3. Pages load data via client-side fetch to API routes
4. API routes use TodoDB static methods for database operations
5. Forms submit via JavaScript to API endpoints
6. Real-time updates through page refreshes and event handling

### Authentication Flow

- Users register/login through dedicated pages
- Sessions stored as HTTP-only cookies with 7-day expiration
- Middleware redirects unauthenticated users to login
- All routes except `/login` and `/api/auth/login` are protected

The database initializes automatically on first run, creating tables and indexes.
