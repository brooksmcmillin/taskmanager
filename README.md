# Task Manager

A modern task management application built with Astro, featuring project organization, time tracking, user authentication, and OAuth 2.0 API access.

> **Security Notice**: This application is designed for educational and personal use. While it implements standard security practices, it has not undergone comprehensive security testing or hardening for production environments handling sensitive data. Use appropriate caution and additional security measures if deploying publicly.

## Features

- **User Authentication**: Secure registration, login, and session management with bcrypt password hashing
- **Project Management**: Create and organize projects with custom colors and descriptions
- **Task Tracking**: Add todos with priorities, descriptions, time estimates, and due dates
- **Time Tracking**: Log actual time spent when completing tasks
- **Calendar View**: Drag-and-drop calendar interface for task scheduling
- **OAuth 2.0 API**: Full OAuth 2.0 authorization server with PKCE support for secure third-party integrations
- **RESTful API**: Complete REST API with OpenAPI 3.0 specification
- **Clean UI**: Custom SCSS design system with responsive layout
- **Database Migrations**: Structured database schema with migration system

## Getting Started

### Prerequisites
- Node.js (v18 or higher)
- npm
- PostgreSQL database

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd taskmanager
```

2. Install dependencies:
```bash
npm install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your database credentials
```

Required environment variables:
- `POSTGRES_DB` - PostgreSQL database name
- `POSTGRES_USER` - PostgreSQL username
- `POSTGRES_PASSWORD` - PostgreSQL password
- `ROOT_DOMAIN` - Your domain (for production)

4. Run database migrations:
```bash
npm run migrate:up
```

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:4321`

### Testing

```bash
npm test
```

Run the test suite to verify functionality. Tests include unit tests for core functionality.

### Build

```bash
npm run build
npm run preview
```

## Project Structure

```
taskmanager/
├── src/
│   ├── components/     # Reusable UI components
│   ├── layouts/        # Page layouts
│   ├── lib/            # Core libraries (auth, db)
│   ├── migrations/     # Database migration files
│   ├── pages/          # Astro pages and API routes
│   │   ├── api/        # REST API endpoints
│   │   └── oauth/      # OAuth consent pages
│   └── styles/         # SCSS stylesheets
├── scripts/            # Build and migration scripts
├── tests/              # Test files
├── openapi.yaml        # OpenAPI 3.0 specification
└── package.json        # Dependencies and scripts
```

## Authentication

The application includes user authentication with session-based auth:

- **Registration**: `/register` - Create new user accounts with email validation
- **Login**: `/login` - Authenticate users with username/password
- **Sessions**: HTTP-only cookies with 7-day expiration
- **Protected Routes**: All routes except login/register require authentication
- **Password Security**: Passwords are hashed using bcrypt with salt rounds

## API Documentation

### REST API

The application provides a comprehensive REST API documented in OpenAPI 3.0 format. See `openapi.yaml` for the complete specification.

#### Main Endpoints:

- **Authentication**: `/api/auth/*` - User registration, login, and logout
- **Projects**: `/api/projects/*` - CRUD operations for projects
- **Todos**: `/api/todos/*` - CRUD operations for todos with filtering and completion tracking

### OAuth 2.0 Server

The application includes a full OAuth 2.0 authorization server for third-party integrations:

- **Authorization**: `/api/oauth/authorize` - OAuth 2.0 authorization endpoint
- **Token**: `/api/oauth/token` - Token exchange endpoint with PKCE support
- **Client Management**: `/api/oauth/clients` - OAuth client registration and management
- **JWKS**: `/api/oauth/jwks` - JSON Web Key Set for token verification

#### Supported OAuth 2.0 Features:
- Authorization Code flow
- PKCE (Proof Key for Code Exchange) for enhanced security
- Refresh tokens
- Scoped access control

## Technology Stack

- **Framework**: Astro 5.x with SSR enabled
- **Database**: PostgreSQL with migration system
- **Authentication**: bcryptjs for password hashing, session-based auth with HTTP-only cookies
- **Styling**: SCSS with custom design system
- **Runtime**: Node.js with @astrojs/node adapter
- **Testing**: Vitest for unit and integration testing
- **OAuth 2.0**: Full authorization server implementation with PKCE support
- **Security**: ESLint security plugins, Husky pre-commit hooks

## Available Scripts

- `npm run dev` - Start development server on port 4321
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run migrate` - Run database migrations
- `npm run migrate:up` - Apply all pending migrations
- `npm run migrate:create` - Create new migration file
- `npm run migrate:rollback` - Rollback last migration
- `npm test` - Run test suite
- `npm run test:ui` - Run tests with Vitest UI
- `npm run test:run` - Run tests once (CI mode)
- `npm run format` - Format code with Prettier
- `npm run format:check` - Check code formatting
- `npm run prepare` - Setup Husky git hooks
