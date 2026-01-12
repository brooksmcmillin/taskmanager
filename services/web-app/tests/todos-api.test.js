import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the database and auth modules
vi.mock('../src/lib/db.js', () => ({
  TodoDB: {
    getTodosFiltered: vi.fn(),
    createTodo: vi.fn(),
    updateTodo: vi.fn(),
    getTodoById: vi.fn(),
    getProjects: vi.fn(),
    getProjectByName: vi.fn(),
    getCategoriesWithCounts: vi.fn(),
    searchTodos: vi.fn(),
  },
}));

vi.mock('../src/lib/auth.js', () => ({
  requireAuth: vi.fn(),
}));

import { TodoDB } from '../src/lib/db.js';
import { requireAuth } from '../src/lib/auth.js';
import { GET as getTodos, POST as createTodo } from '../src/pages/api/todos.js';
import { PUT as updateTodo } from '../src/pages/api/todos/[id].js';
import { GET as getCategories } from '../src/pages/api/categories.js';
import { GET as searchTasks } from '../src/pages/api/tasks/search.js';

const mockSession = { user_id: 1, username: 'testuser' };

const createMockRequest = (url, options = {}) => {
  return new Request(url, options);
};

describe('GET /api/todos', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should return tasks with proper format', async () => {
    const mockTodos = [
      {
        id: 1,
        title: 'Test Task',
        description: 'Test description',
        due_date: new Date('2025-12-20'),
        status: 'pending',
        project_name: 'work',
        project_color: '#3b82f6',
        priority: 'high',
        tags: ['urgent'],
        created_at: new Date('2025-12-01'),
        updated_at: new Date('2025-12-10'),
      },
    ];

    TodoDB.getTodosFiltered.mockResolvedValue(mockTodos);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });

    expect(response.status).toBe(200);
    const data = await response.json();

    expect(data).toHaveProperty('tasks');
    expect(data.tasks).toHaveLength(1);
    expect(data.tasks[0]).toEqual({
      id: 1,
      title: 'Test Task',
      description: 'Test description',
      due_date: '2025-12-20',
      status: 'pending',
      category: 'work',
      project_name: 'work',
      project_color: '#3b82f6',
      priority: 'high',
      tags: ['urgent'],
      created_at: '2025-12-01',
      updated_at: '2025-12-10',
    });
  });

  it('should return raw numeric id for frontend compatibility', async () => {
    const mockTodos = [
      { id: 42, title: 'Test', created_at: new Date(), updated_at: new Date() },
    ];
    TodoDB.getTodosFiltered.mockResolvedValue(mockTodos);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0].id).toBe(42);
    expect(typeof data.tasks[0].id).toBe('number');
  });

  it('should include project_name and project_color for frontend display', async () => {
    const mockTodos = [
      {
        id: 1,
        title: 'Task with project',
        project_name: 'Home Improvement',
        project_color: '#10b981',
        created_at: new Date(),
        updated_at: new Date(),
      },
    ];
    TodoDB.getTodosFiltered.mockResolvedValue(mockTodos);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0]).toHaveProperty('project_name', 'Home Improvement');
    expect(data.tasks[0]).toHaveProperty('project_color', '#10b981');
  });

  it('should handle null project_name and project_color', async () => {
    const mockTodos = [
      {
        id: 1,
        title: 'Task without project',
        project_name: null,
        project_color: null,
        created_at: new Date(),
        updated_at: new Date(),
      },
    ];
    TodoDB.getTodosFiltered.mockResolvedValue(mockTodos);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0].project_name).toBeNull();
    expect(data.tasks[0].project_color).toBeNull();
  });

  it('should wrap response in tasks object for frontend compatibility', async () => {
    const mockTodos = [
      {
        id: 1,
        title: 'Task 1',
        created_at: new Date(),
        updated_at: new Date(),
      },
      {
        id: 2,
        title: 'Task 2',
        created_at: new Date(),
        updated_at: new Date(),
      },
    ];
    TodoDB.getTodosFiltered.mockResolvedValue(mockTodos);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });
    const data = await response.json();

    // Response must be { tasks: [...] } not a raw array
    expect(data).toHaveProperty('tasks');
    expect(Array.isArray(data.tasks)).toBe(true);
    expect(Array.isArray(data)).toBe(false);
  });

  it('should pass filter parameters to database', async () => {
    TodoDB.getTodosFiltered.mockResolvedValue([]);

    const request = createMockRequest(
      'http://localhost:3000/api/todos?status=pending&start_date=2025-12-01&end_date=2025-12-31&category=work&limit=10'
    );
    await getTodos({ url: request.url, request });

    expect(TodoDB.getTodosFiltered).toHaveBeenCalledWith(1, {
      projectId: null,
      status: 'pending',
      startDate: '2025-12-01',
      endDate: '2025-12-31',
      category: 'work',
      limit: 10,
    });
  });

  it('should handle empty results', async () => {
    TodoDB.getTodosFiltered.mockResolvedValue([]);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.tasks).toEqual([]);
  });

  it('should parse JSON tags when stored as string', async () => {
    const mockTodos = [
      {
        id: 1,
        title: 'Test',
        tags: '["tag1", "tag2"]',
        created_at: new Date(),
        updated_at: new Date(),
      },
    ];

    TodoDB.getTodosFiltered.mockResolvedValue(mockTodos);

    const request = createMockRequest('http://localhost:3000/api/todos');
    const response = await getTodos({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0].tags).toEqual(['tag1', 'tag2']);
  });
});

describe('POST /api/todos', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should create a task and return proper format', async () => {
    TodoDB.createTodo.mockResolvedValue({ id: 123 });

    const request = createMockRequest('http://localhost:3000/api/todos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'New Task',
        description: 'Task description',
        priority: 'high',
      }),
    });

    const response = await createTodo({ request });

    expect(response.status).toBe(201);
    const data = await response.json();

    // createdResponse wraps data in { data: ... }
    expect(data).toEqual({
      data: {
        id: 123,
        title: 'New Task',
      },
    });
  });

  it('should map category to project_id when provided', async () => {
    // Mock getProjectByName to return a project when searching by category name
    TodoDB.getProjectByName.mockResolvedValue({ id: 5, name: 'Work' });
    TodoDB.createTodo.mockResolvedValue({ id: 456 });

    const request = createMockRequest('http://localhost:3000/api/todos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Categorized Task',
        category: 'work',
      }),
    });

    await createTodo({ request });

    // Verify getProjectByName was called with user_id and category name
    expect(TodoDB.getProjectByName).toHaveBeenCalledWith(1, 'work');
    // Verify createTodo was called with project_id mapped from category
    // Note: category remains in todoData alongside project_id
    expect(TodoDB.createTodo).toHaveBeenCalledWith(1, {
      title: 'Categorized Task',
      category: 'work',
      project_id: 5,
    });
  });
});

describe('PUT /api/todos/[id]', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should update a task and return proper format', async () => {
    TodoDB.getTodoById.mockResolvedValue({ id: 123, title: 'Old Title' });
    TodoDB.updateTodo.mockResolvedValue({ id: 123 });

    const request = createMockRequest('http://localhost:3000/api/todos/123', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        title: 'Updated Title',
        priority: 'urgent',
      }),
    });

    const response = await updateTodo({ params: { id: '123' }, request });

    expect(response.status).toBe(200);
    const data = await response.json();

    expect(data).toEqual({
      id: 123,
      updated_fields: ['title', 'priority'],
      status: 'updated',
    });
  });

  it('should return 404 for non-existent task', async () => {
    TodoDB.getTodoById.mockResolvedValue(null);

    const request = createMockRequest('http://localhost:3000/api/todos/999', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Test' }),
    });

    const response = await updateTodo({ params: { id: '999' }, request });

    expect(response.status).toBe(404);
    const data = await response.json();
    // New error format uses { error: { code, message } }
    expect(data.error.code).toBe('NOT_FOUND_004');
    expect(data.error.message).toBe('Task not found');
  });

  it('should return 400 for invalid todo ID', async () => {
    const request = createMockRequest(
      'http://localhost:3000/api/todos/invalid',
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'Test' }),
      }
    );

    const response = await updateTodo({ params: { id: 'invalid' }, request });

    expect(response.status).toBe(400);
  });

  it('should map category to project_id when updating', async () => {
    TodoDB.getTodoById.mockResolvedValue({ id: 123 });
    TodoDB.getProjectByName.mockResolvedValue({ id: 10, name: 'Research' });
    TodoDB.updateTodo.mockResolvedValue({ id: 123 });

    const request = createMockRequest('http://localhost:3000/api/todos/123', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: 'research' }),
    });

    await updateTodo({ params: { id: '123' }, request });

    // Verify getProjectByName was called with user_id and category name
    expect(TodoDB.getProjectByName).toHaveBeenCalledWith(1, 'research');
    // Verify updateTodo was called with project_id mapped from category
    // Note: PUT handler removes category after mapping to project_id
    expect(TodoDB.updateTodo).toHaveBeenCalledWith(123, 1, { project_id: 10 });
  });
});

describe('GET /api/categories', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should return categories with task counts', async () => {
    const mockCategories = [
      { name: 'work', task_count: '15' },
      { name: 'personal', task_count: '8' },
      { name: 'research', task_count: '5' },
    ];

    TodoDB.getCategoriesWithCounts.mockResolvedValue(mockCategories);

    const request = createMockRequest('http://localhost:3000/api/categories');
    const response = await getCategories({ request });

    expect(response.status).toBe(200);
    const data = await response.json();

    expect(data).toEqual({
      categories: [
        { name: 'work', task_count: 15 },
        { name: 'personal', task_count: 8 },
        { name: 'research', task_count: 5 },
      ],
    });
  });

  it('should return empty array when no categories exist', async () => {
    TodoDB.getCategoriesWithCounts.mockResolvedValue([]);

    const request = createMockRequest('http://localhost:3000/api/categories');
    const response = await getCategories({ request });

    const data = await response.json();
    expect(data.categories).toEqual([]);
  });
});

describe('GET /api/tasks/search', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should search tasks and return results with count', async () => {
    const mockResults = [
      {
        id: 1,
        title: 'Meeting notes',
        description: 'Notes from team meeting',
        status: 'completed',
        project_name: 'work',
        priority: 'medium',
        tags: [],
        created_at: new Date('2025-12-01'),
        updated_at: new Date('2025-12-10'),
      },
      {
        id: 2,
        title: 'Research meeting agenda',
        status: 'pending',
        project_name: 'research',
        priority: 'high',
        tags: ['urgent'],
        created_at: new Date('2025-12-05'),
        updated_at: new Date('2025-12-05'),
      },
    ];

    TodoDB.searchTodos.mockResolvedValue(mockResults);

    const request = createMockRequest(
      'http://localhost:3000/api/tasks/search?query=meeting'
    );
    const response = await searchTasks({ url: request.url, request });

    expect(response.status).toBe(200);
    const data = await response.json();

    expect(data.tasks).toHaveLength(2);
    expect(data.count).toBe(2);
    expect(TodoDB.searchTodos).toHaveBeenCalledWith(1, 'meeting', null);
  });

  it('should filter search by category', async () => {
    TodoDB.searchTodos.mockResolvedValue([]);

    const request = createMockRequest(
      'http://localhost:3000/api/tasks/search?query=meeting&category=work'
    );
    await searchTasks({ url: request.url, request });

    expect(TodoDB.searchTodos).toHaveBeenCalledWith(1, 'meeting', 'work');
  });

  it('should return 400 when query is missing', async () => {
    const request = createMockRequest('http://localhost:3000/api/tasks/search');
    const response = await searchTasks({ url: request.url, request });

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error).toBe('Query parameter is required');
  });

  it('should return empty results for no matches', async () => {
    TodoDB.searchTodos.mockResolvedValue([]);

    const request = createMockRequest(
      'http://localhost:3000/api/tasks/search?query=nonexistent'
    );
    const response = await searchTasks({ url: request.url, request });

    const data = await response.json();
    expect(data.tasks).toEqual([]);
    expect(data.count).toBe(0);
  });
});
