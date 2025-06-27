import { describe, it, expect, beforeEach, vi } from 'vitest';
import { GET as todosGet, POST as todosPost, PUT as todosPut } from '../../src/pages/api/todos.js';
import { POST as completePost } from '../../src/pages/api/todos/[id]/complete.js';
import { Auth } from '../../src/lib/auth.js';
import { TodoDB } from '../../src/lib/db.js';

// Mock dependencies
vi.mock('../../src/lib/auth.js', () => ({
  Auth: {
    getSessionFromRequest: vi.fn(),
    getSessionUser: vi.fn()
  }
}));

vi.mock('../../src/lib/db.js', () => ({
  TodoDB: {
    getTodos: vi.fn(),
    createTodo: vi.fn(),
    updateTodo: vi.fn(),
    completeTodo: vi.fn()
  }
}));

describe('Todos API Endpoints', () => {
  const mockSession = {
    user_id: 1,
    username: 'testuser',
    email: 'test@example.com'
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('GET /api/todos', () => {
    it('should get todos for authenticated user', async () => {
      const mockTodos = [
        { id: 1, title: 'Test Todo 1', status: 'pending' },
        { id: 2, title: 'Test Todo 2', status: 'completed' }
      ];

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.getTodos.mockResolvedValue(mockTodos);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') }
      };
      const url = 'http://localhost/api/todos';

      const response = await todosGet({ url, request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData).toEqual(mockTodos);
      expect(TodoDB.getTodos).toHaveBeenCalledWith(1, null, null, null);
    });

    it('should filter todos by project_id', async () => {
      const mockTodos = [{ id: 1, title: 'Project Todo', project_id: 5 }];

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.getTodos.mockResolvedValue(mockTodos);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') }
      };
      const url = 'http://localhost/api/todos?project_id=5';

      const response = await todosGet({ url, request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData).toEqual(mockTodos);
      expect(TodoDB.getTodos).toHaveBeenCalledWith(1, '5', null, null);
    });

    it('should filter todos by status', async () => {
      const mockTodos = [{ id: 1, title: 'Pending Todo', status: 'pending' }];

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.getTodos.mockResolvedValue(mockTodos);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') }
      };
      const url = 'http://localhost/api/todos?status=pending';

      const response = await todosGet({ url, request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData).toEqual(mockTodos);
      expect(TodoDB.getTodos).toHaveBeenCalledWith(1, null, 'pending', null);
    });

    it('should return 401 for unauthenticated user', async () => {
      Auth.getSessionFromRequest.mockReturnValue('invalid-session');
      Auth.getSessionUser.mockResolvedValue(null);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=invalid-session') }
      };
      const url = 'http://localhost/api/todos';

      const response = await todosGet({ url, request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Authentication required');
    });
  });

  describe('POST /api/todos', () => {
    it('should create new todo successfully', async () => {
      const todoData = {
        title: 'New Todo',
        description: 'Todo description',
        project_id: 1,
        priority: 3
      };

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.createTodo.mockResolvedValue({ lastInsertRowid: 123 });

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue(todoData)
      };

      const response = await todosPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(201);
      expect(responseData.id).toBe(123);
      expect(TodoDB.createTodo).toHaveBeenCalledWith(1, todoData);
    });

    it('should return 401 for unauthenticated user', async () => {
      Auth.getSessionFromRequest.mockReturnValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const request = {
        headers: { get: vi.fn().mockReturnValue(null) },
        json: vi.fn().mockResolvedValue({ title: 'Test Todo' })
      };

      const response = await todosPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Authentication required');
    });

    it('should handle database errors', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.createTodo.mockRejectedValue(new Error('Database error'));

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue({ title: 'Test Todo' })
      };

      const response = await todosPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(500);
      expect(responseData.error).toBe('Database error');
    });
  });

  describe('PUT /api/todos', () => {
    it('should update todo successfully', async () => {
      const updateData = {
        id: 1,
        title: 'Updated Todo',
        status: 'in_progress'
      };

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.updateTodo.mockResolvedValue({ id: 1, title: 'Updated Todo' });

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue(updateData)
      };

      const response = await todosPut({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData.success).toBe(true);
      expect(TodoDB.updateTodo).toHaveBeenCalledWith(1, 1, {
        title: 'Updated Todo',
        status: 'in_progress'
      });
    });

    it('should return 401 for unauthenticated user', async () => {
      Auth.getSessionFromRequest.mockReturnValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const request = {
        headers: { get: vi.fn().mockReturnValue(null) },
        json: vi.fn().mockResolvedValue({ id: 1, title: 'Updated Todo' })
      };

      const response = await todosPut({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Authentication required');
    });
  });

  describe('POST /api/todos/[id]/complete', () => {
    it('should complete todo successfully', async () => {
      const completedTodo = {
        id: 1,
        title: 'Completed Todo',
        status: 'completed',
        actual_hours: 2.5
      };

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.completeTodo.mockResolvedValue(completedTodo);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue({ actual_hours: 2.5 })
      };
      const params = { id: '1' };

      const response = await completePost({ request, params });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData.success).toBe(true);
      expect(TodoDB.completeTodo).toHaveBeenCalledWith(1, 1, 2.5);
    });

    it('should return 400 for missing id', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue({ actual_hours: 2.5 })
      };
      const params = {}; // missing id

      const response = await completePost({ request, params });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
    });

    it('should return 400 for missing actual_hours', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue({}) // missing actual_hours
      };
      const params = { id: '1' };

      const response = await completePost({ request, params });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(400);
    });

    it('should return 401 for unauthenticated user', async () => {
      Auth.getSessionFromRequest.mockReturnValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const request = {
        headers: { get: vi.fn().mockReturnValue(null) },
        json: vi.fn().mockResolvedValue({ actual_hours: 2.5 })
      };
      const params = { id: '1' };

      const response = await completePost({ request, params });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Authentication required');
    });
  });
});
