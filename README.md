# Task Manager

A modern task management application built with Astro, featuring project organization, time tracking, and a clean design system.

## Features

- **Project Management**: Create and organize projects with custom colors
- **Task Tracking**: Add todos with priorities, descriptions, and time estimates
- **Time Tracking**: Log actual time spent when completing tasks
- **Clean UI**: Custom CSS design system with responsive layout
- **Real-time Updates**: Dynamic loading and updates without page refreshes

## Getting Started

### Prerequisites
- Node.js (v18 or higher)
- npm

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:4321`

### Build

```bash
npm run build
npm run preview
```

## API Endpoints

### Projects

#### GET /api/projects
Get all active projects.

**Response:**
```json
[
  {
    "id": 1,
    "name": "Website Redesign",
    "description": "Complete overhaul of company website",
    "color": "#3b82f6",
    "created_at": "2024-01-01T00:00:00.000Z",
    "is_active": 1
  }
]
```

#### POST /api/projects
Create a new project.

**Request Body:**
```json
{
  "name": "Project Name",
  "description": "Optional description",
  "color": "#3b82f6"
}
```

**Response:**
```json
{
  "id": 1
}
```

### Todos

#### GET /api/todos
Get todos with optional filtering.

**Query Parameters:**
- `project_id` (optional): Filter by project ID
- `status` (optional): Filter by status (`pending`, `in_progress`, `completed`, `cancelled`)

**Examples:**
- `/api/todos` - Get all todos
- `/api/todos?status=pending` - Get pending todos
- `/api/todos?project_id=1` - Get todos for project 1
- `/api/todos?project_id=1&status=pending` - Get pending todos for project 1

**Response:**
```json
[
  {
    "id": 1,
    "project_id": 1,
    "title": "Update homepage design",
    "description": "Implement new design mockups",
    "priority": "high",
    "estimated_hours": 4.0,
    "actual_hours": null,
    "status": "pending",
    "due_date": "2024-01-15",
    "completed_date": null,
    "tags": "[\"frontend\", \"design\"]",
    "context": "work",
    "created_at": "2024-01-01T00:00:00.000Z",
    "updated_at": "2024-01-01T00:00:00.000Z",
    "project_name": "Website Redesign",
    "project_color": "#3b82f6"
  }
]
```

#### POST /api/todos
Create a new todo.

**Request Body:**
```json
{
  "project_id": 1,
  "title": "Task title",
  "description": "Optional description",
  "priority": "medium",
  "estimated_hours": 2.5,
  "due_date": "2024-01-15",
  "tags": ["frontend", "urgent"],
  "context": "work"
}
```

**Response:**
```json
{
  "id": 1
}
```

**Field Details:**
- `priority`: `low`, `medium`, `high`, or `urgent`
- `status`: `pending`, `in_progress`, `completed`, or `cancelled` (defaults to `pending`)
- `tags`: Array of strings (stored as JSON)
- `due_date`: ISO date string (optional)

#### PUT /api/todos
Update an existing todo.

**Request Body:**
```json
{
  "id": 1,
  "title": "Updated title",
  "status": "in_progress",
  "priority": "high"
}
```

**Response:**
```json
{
  "success": true
}
```

#### POST /api/todos/[id]/complete
Mark a todo as completed and log actual time spent.

**Request Body:**
```json
{
  "actual_hours": 3.5
}
```

**Response:**
```json
{
  "success": true
}
```

## Database Schema

### Projects Table
- `id`: Primary key
- `name`: Project name (unique)
- `description`: Optional description
- `color`: Hex color code (default: #3b82f6)
- `created_at`: Creation timestamp
- `is_active`: Boolean flag (default: true)

### Todos Table
- `id`: Primary key
- `project_id`: Foreign key to projects table
- `title`: Task title
- `description`: Optional description
- `priority`: Enum (low, medium, high, urgent)
- `estimated_hours`: Estimated time (default: 1.0)
- `actual_hours`: Time actually spent (set on completion)
- `status`: Enum (pending, in_progress, completed, cancelled)
- `due_date`: Optional due date
- `completed_date`: Set automatically when completed
- `tags`: JSON array of tag strings
- `context`: Task context (default: 'work')
- `created_at`, `updated_at`: Timestamps

## Project Structure

```
src/
├── components/
│   ├── Navigation.astro    # Main navigation bar
│   └── TodoForm.astro      # Todo creation form
├── layouts/
│   └── Layout.astro        # Base layout with global CSS
├── lib/
│   └── db.js              # Database operations (TodoDB class)
├── pages/
│   ├── api/               # API endpoints
│   │   ├── projects.js    # Project CRUD operations
│   │   ├── todos.js       # Todo CRUD operations
│   │   └── todos/[id]/
│   │       └── complete.js # Todo completion endpoint
│   ├── index.astro        # Main todos page
│   └── projects.astro     # Project management page
└── styles/
    └── global.css         # Custom design system
```

## Technology Stack

- **Framework**: Astro with SSR
- **Database**: SQLite with better-sqlite3
- **Styling**: Custom CSS design system
- **Runtime**: Node.js with standalone adapter
