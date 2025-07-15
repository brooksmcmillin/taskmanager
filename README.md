# Task Manager

A modern task management application built with Astro, featuring project organization, time tracking, user authentication, and OAuth2 API access.

> **Security Notice**: This application is designed for educational and personal use. While it implements standard security practices, it has not undergone comprehensive security testing or hardening for production environments handling sensitive data. Use appropriate caution and additional security measures if deploying publicly.

## Features

- **User Authentication**: Secure registration, login, and session management
- **Project Management**: Create and organize projects with custom colors and descriptions
- **Task Tracking**: Add todos with priorities, descriptions, time estimates, and due dates
- **Time Tracking**: Log actual time spent when completing tasks
- **Calendar View**: Drag-and-drop calendar interface for task scheduling
- **OAuth2 API**: RESTful API with OAuth2 authentication for third-party integrations
- **Clean UI**: Custom CSS design system with responsive layout
- **Database Migrations**: Structured database schema with migration system

## Getting Started

### Prerequisites
- Node.js (v18 or higher)
- npm
- PostgreSQL database (for production) or SQLite (for development)

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

4. Run database migrations:
```bash
npm run migrate:up
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

## Authentication

The application includes user authentication with session-based auth:

- **Registration**: `/register` - Create new user accounts
- **Login**: `/login` - Authenticate users with username/password
- **Sessions**: HTTP-only cookies with 7-day expiration
- **Protected Routes**: All routes except login/register require authentication

## OAuth2 API

The application provides OAuth2 endpoints for third-party integrations:

- **Authorization**: `/api/oauth/authorize` - OAuth2 authorization endpoint
- **Token**: `/api/oauth/token` - Token exchange endpoint
- **Client Management**: `/api/oauth/clients` - OAuth client registration
- **JWKS**: `/api/oauth/jwks` - JSON Web Key Set for token verification

## Technology Stack

- **Framework**: Astro with SSR enabled
- **Database**: PostgreSQL (production)
- **Authentication**: bcryptjs with session-based auth
- **Styling**: SCSS with custom design system
- **Runtime**: Node.js with standalone adapter
- **Testing**: Vitest with supertest for API testing
- **OAuth2**: JSON Web Tokens (JWT) for API authentication

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run migrate` - Run database migrations
- `npm run migrate:up` - Apply migrations
- `npm run migrate:create` - Create new migration
- `npm run migrate:rollback` - Rollback last migration
- `npm test` - Run test suite
- `npm run test:ui` - Run tests with UI
- `npm run format` - Format code with Prettier
