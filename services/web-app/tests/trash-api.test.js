import { describe, it, expect, beforeEach, vi } from 'vitest';

// Mock the database and auth modules
vi.mock('../src/lib/db.js', () => ({
  TodoDB: {
    getDeletedTodos: vi.fn(),
    getDeletedTodoById: vi.fn(),
    searchDeletedTodos: vi.fn(),
    restoreTodo: vi.fn(),
  },
}));

vi.mock('../src/lib/auth.js', () => ({
  requireAuth: vi.fn(),
}));

import { TodoDB } from '../src/lib/db.js';
import { requireAuth } from '../src/lib/auth.js';
import { GET as getTrash } from '../src/pages/api/trash.js';
import { POST as restoreTodo } from '../src/pages/api/trash/[id]/restore.js';

const mockSession = { user_id: 1, username: 'testuser' };

const createMockRequest = (url, options = {}) => {
  return new Request(url, options);
};

describe('GET /api/trash', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should return deleted tasks with proper format', async () => {
    const mockDeletedTodos = [
      {
        id: 1,
        title: 'Deleted Task',
        description: 'This was deleted',
        due_date: new Date('2025-12-20'),
        status: 'pending',
        project_name: 'work',
        project_color: '#3b82f6',
        priority: 'high',
        tags: ['important'],
        deleted_at: new Date('2025-12-25'),
        created_at: new Date('2025-12-01'),
      },
    ];

    TodoDB.getDeletedTodos.mockResolvedValue(mockDeletedTodos);

    const request = createMockRequest('http://localhost:3000/api/trash');
    const response = await getTrash({ url: request.url, request });

    expect(response.status).toBe(200);
    const data = await response.json();

    expect(data).toHaveProperty('tasks');
    expect(data).toHaveProperty('count', 1);
    expect(data.tasks).toHaveLength(1);
    expect(data.tasks[0]).toEqual({
      id: 1,
      title: 'Deleted Task',
      description: 'This was deleted',
      due_date: '2025-12-20',
      status: 'pending',
      project_name: 'work',
      project_color: '#3b82f6',
      priority: 'high',
      tags: ['important'],
      deleted_at: '2025-12-25',
      created_at: '2025-12-01',
    });
  });

  it('should handle empty trash', async () => {
    TodoDB.getDeletedTodos.mockResolvedValue([]);

    const request = createMockRequest('http://localhost:3000/api/trash');
    const response = await getTrash({ url: request.url, request });

    expect(response.status).toBe(200);
    const data = await response.json();
    expect(data.tasks).toEqual([]);
    expect(data.count).toBe(0);
  });

  it('should search deleted tasks when query parameter is provided', async () => {
    const mockSearchResults = [
      {
        id: 2,
        title: 'Meeting notes',
        description: 'Notes from meeting',
        deleted_at: new Date('2025-12-24'),
        created_at: new Date('2025-12-01'),
      },
    ];

    TodoDB.searchDeletedTodos.mockResolvedValue(mockSearchResults);

    const request = createMockRequest(
      'http://localhost:3000/api/trash?query=meeting'
    );
    const response = await getTrash({ url: request.url, request });

    expect(response.status).toBe(200);
    expect(TodoDB.searchDeletedTodos).toHaveBeenCalledWith(1, 'meeting');
    expect(TodoDB.getDeletedTodos).not.toHaveBeenCalled();

    const data = await response.json();
    expect(data.tasks).toHaveLength(1);
    expect(data.count).toBe(1);
  });

  it('should ignore empty query parameter and return all deleted tasks', async () => {
    TodoDB.getDeletedTodos.mockResolvedValue([]);

    const request = createMockRequest('http://localhost:3000/api/trash?query=');
    const response = await getTrash({ url: request.url, request });

    expect(TodoDB.getDeletedTodos).toHaveBeenCalledWith(1);
    expect(TodoDB.searchDeletedTodos).not.toHaveBeenCalled();
  });

  it('should ignore whitespace-only query parameter', async () => {
    TodoDB.getDeletedTodos.mockResolvedValue([]);

    const request = createMockRequest(
      'http://localhost:3000/api/trash?query=%20%20'
    );
    const response = await getTrash({ url: request.url, request });

    expect(TodoDB.getDeletedTodos).toHaveBeenCalledWith(1);
    expect(TodoDB.searchDeletedTodos).not.toHaveBeenCalled();
  });

  it('should handle null project_name and project_color', async () => {
    const mockDeletedTodos = [
      {
        id: 1,
        title: 'Task without project',
        project_name: null,
        project_color: null,
        deleted_at: new Date('2025-12-25'),
        created_at: new Date('2025-12-01'),
      },
    ];

    TodoDB.getDeletedTodos.mockResolvedValue(mockDeletedTodos);

    const request = createMockRequest('http://localhost:3000/api/trash');
    const response = await getTrash({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0].project_name).toBeNull();
    expect(data.tasks[0].project_color).toBeNull();
  });

  it('should parse JSON tags when stored as string', async () => {
    const mockDeletedTodos = [
      {
        id: 1,
        title: 'Test',
        tags: '["tag1", "tag2"]',
        deleted_at: new Date('2025-12-25'),
        created_at: new Date('2025-12-01'),
      },
    ];

    TodoDB.getDeletedTodos.mockResolvedValue(mockDeletedTodos);

    const request = createMockRequest('http://localhost:3000/api/trash');
    const response = await getTrash({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0].tags).toEqual(['tag1', 'tag2']);
  });

  it('should handle missing tags gracefully', async () => {
    const mockDeletedTodos = [
      {
        id: 1,
        title: 'Test',
        tags: null,
        deleted_at: new Date('2025-12-25'),
        created_at: new Date('2025-12-01'),
      },
    ];

    TodoDB.getDeletedTodos.mockResolvedValue(mockDeletedTodos);

    const request = createMockRequest('http://localhost:3000/api/trash');
    const response = await getTrash({ url: request.url, request });
    const data = await response.json();

    expect(data.tasks[0].tags).toEqual([]);
  });

  it('should return 401 when not authenticated', async () => {
    requireAuth.mockRejectedValue(new Error('Authentication required'));

    const request = createMockRequest('http://localhost:3000/api/trash');
    const response = await getTrash({ url: request.url, request });

    expect(response.status).toBe(401);
    const data = await response.json();
    expect(data.error.code).toBe('AUTH_002');
  });
});

describe('POST /api/trash/[id]/restore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    requireAuth.mockResolvedValue(mockSession);
  });

  it('should restore a deleted task', async () => {
    const mockDeletedTodo = {
      id: 123,
      title: 'Deleted Task',
      deleted_at: new Date('2025-12-25'),
    };

    TodoDB.getDeletedTodoById.mockResolvedValue(mockDeletedTodo);
    TodoDB.restoreTodo.mockResolvedValue({ id: 123, deleted_at: null });

    const request = createMockRequest(
      'http://localhost:3000/api/trash/123/restore',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const response = await restoreTodo({ params: { id: '123' }, request });

    expect(response.status).toBe(200);
    const data = await response.json();

    expect(data).toEqual({
      restored: true,
      id: 123,
    });
    expect(TodoDB.getDeletedTodoById).toHaveBeenCalledWith(123, 1);
    expect(TodoDB.restoreTodo).toHaveBeenCalledWith(123, 1);
  });

  it('should return 404 when deleted task does not exist', async () => {
    TodoDB.getDeletedTodoById.mockResolvedValue(null);

    const request = createMockRequest(
      'http://localhost:3000/api/trash/999/restore',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const response = await restoreTodo({ params: { id: '999' }, request });

    expect(response.status).toBe(404);
    const data = await response.json();
    expect(data.error.message).toBe('Deleted task not found');
    expect(TodoDB.restoreTodo).not.toHaveBeenCalled();
  });

  it('should return 400 for invalid todo ID', async () => {
    const request = createMockRequest(
      'http://localhost:3000/api/trash/invalid/restore',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const response = await restoreTodo({ params: { id: 'invalid' }, request });

    expect(response.status).toBe(400);
    const data = await response.json();
    expect(data.error.message).toContain('Todo ID');
  });

  it('should return 400 for negative todo ID', async () => {
    const request = createMockRequest(
      'http://localhost:3000/api/trash/-1/restore',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const response = await restoreTodo({ params: { id: '-1' }, request });

    expect(response.status).toBe(400);
  });

  it('should return 401 when not authenticated', async () => {
    requireAuth.mockRejectedValue(new Error('Authentication required'));

    const request = createMockRequest(
      'http://localhost:3000/api/trash/123/restore',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      }
    );

    const response = await restoreTodo({ params: { id: '123' }, request });

    expect(response.status).toBe(401);
    const data = await response.json();
    expect(data.error.code).toBe('AUTH_002');
  });
});
