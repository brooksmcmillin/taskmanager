# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

| Command | Purpose |
|---------|---------|
| `npm run dev` | Start development server at localhost:4321 |
| `npm run build` | Build production site to ./dist/ |
| `npm run preview` | Preview production build locally |

## Architecture Overview

This is an Astro-based task management application with server-side rendering and API routes.

### Core Architecture
- **Frontend**: Astro with SSR enabled, custom CSS design system
- **Backend**: Astro API routes handling REST endpoints
- **Database**: SQLite with better-sqlite3, single file (`todos.db`)
- **Styling**: Custom CSS design system in `/src/styles/global.css`

### Database Schema
The application uses SQLite with two main tables:
- `projects`: Project management with name, description, color
- `todos`: Task items linked to projects with priority, status, time tracking

### Key Components Structure
- **Layout System**: `src/layouts/Layout.astro` includes global CSS and navigation
- **Navigation**: `src/components/Navigation.astro` - reusable nav with active states
- **Forms**: `src/components/TodoForm.astro` - handles todo creation with project selection
- **Database Layer**: `src/lib/db.js` - TodoDB class with static methods for all database operations

### API Architecture
RESTful API endpoints in `/src/pages/api/`:
- `/api/todos` - GET (with filters), POST, PUT for todo operations
- `/api/projects` - GET, POST for project management  
- `/api/todos/[id]/complete` - POST for completing todos with time tracking

### CSS Design System
Custom design system with CSS variables and utility classes:
- Component classes: `.card`, `.btn`, `.form-input`, `.nav-link`
- Utility classes for layout, spacing, typography
- Responsive design with container and grid utilities

### Data Flow
1. Pages load data via client-side fetch to API routes
2. API routes use TodoDB static methods for database operations
3. Forms submit via JavaScript to API endpoints
4. Real-time updates through page refreshes and event handling

The database initializes automatically on first run, creating tables and indexes.