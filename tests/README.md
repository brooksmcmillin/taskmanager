# Test Suite for Task Manager Application

This directory contains comprehensive unit tests for the task management application, covering database operations, authentication, and API endpoints.

## Test Structure

```
tests/
├── setup.js              # Test environment setup
├── lib/
│   ├── db.test.js        # Database layer tests (TodoDB class)
│   └── auth.test.js      # Authentication tests (Auth class)
└── api/
    ├── auth.test.js      # Authentication API endpoints
    ├── todos.test.js     # Todo management API endpoints
    └── projects.test.js  # Project management API endpoints
```

## Running Tests

```bash
# Run all tests
npm test

# Run tests with UI
npm run test:ui

# Run tests once (CI mode)
npm run test:run

# Run specific test file
npx vitest run tests/lib/db.test.js

# Run tests in watch mode
npx vitest
```

## Test Coverage

### Database Tests (`tests/lib/db.test.js`)

- ✅ User CRUD operations
- ✅ Session management
- ✅ Project management
- ✅ Todo operations
- ✅ Analytics queries
- ✅ Data isolation and cleanup

### Authentication Tests (`tests/lib/auth.test.js`)

- ✅ Password hashing and verification
- ✅ User registration and login
- ✅ Session creation and management
- ✅ Cookie handling
- ✅ Error handling for invalid credentials

### API Endpoint Tests

- ✅ **Auth API** (`tests/api/auth.test.js`)
  - POST /api/auth/login
  - POST /api/auth/register
  - GET /api/auth/me
  - POST /api/auth/logout

- ✅ **Todos API** (`tests/api/todos.test.js`)
  - GET /api/todos (with filtering)
  - POST /api/todos
  - PUT /api/todos
  - POST /api/todos/[id]/complete

- ✅ **Projects API** (`tests/api/projects.test.js`)
  - GET /api/projects
  - POST /api/projects

## Test Environment

The tests use a separate test database to avoid conflicts with development data:

- Database: `taskmanager_test` (automatically appended to your main DB name)
- Environment variables loaded from `.env.test`
- Clean state before/after each test suite

## Testing Frameworks

- **Vitest**: Fast, modern testing framework
- **Mocking**: Extensive use of vi.mock() for isolated unit testing
- **Supertest**: HTTP assertion library (available for integration tests)

## Test Categories

### Unit Tests

- Database operations (TodoDB class)
- Authentication logic (Auth class)
- API endpoint handlers

### Integration Tests

- Full API request/response cycles
- Database interactions
- Authentication flows

### Security Tests

- Authentication bypass attempts
- Data isolation verification
- Input validation

## Key Testing Patterns

1. **Mocking**: Dependencies are mocked to isolate units under test
2. **Setup/Teardown**: Clean database state for each test
3. **Error Scenarios**: Testing both success and failure paths
4. **Security**: Verifying authentication and authorization
5. **Data Isolation**: Ensuring users can only access their own data

## Adding New Tests

When adding new features:

1. Add unit tests for new functions/classes
2. Add API tests for new endpoints
3. Include both success and error scenarios
4. Test authentication requirements
5. Verify data isolation

## Common Test Patterns

```javascript
// Mocking dependencies
vi.mock('../../src/lib/db.js', () => ({
  TodoDB: {
    methodName: vi.fn(),
  },
}));

// Testing API endpoints
const response = await endpointFunction({ request, params });
const responseData = JSON.parse(await response.text());
expect(response.status).toBe(200);

// Authentication testing
Auth.getSessionUser.mockResolvedValue(mockUser);
// ... test authenticated behavior

Auth.getSessionUser.mockResolvedValue(null);
// ... test unauthenticated behavior
```
