import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  GET as projectsGet,
  POST as projectsPost,
} from '../../src/pages/api/projects.js';
import { Auth } from '../../src/lib/auth.js';
import { TodoDB } from '../../src/lib/db.js';

// Mock dependencies
vi.mock('../../src/lib/auth.js', () => ({
  Auth: {
    getSessionFromRequest: vi.fn(),
    getSessionUser: vi.fn(),
  },
}));

vi.mock('../../src/lib/db.js', () => ({
  TodoDB: {
    getProjects: vi.fn(),
    createProject: vi.fn(),
  },
}));

describe('Projects API Endpoints', () => {
  const mockSession = {
    user_id: 1,
    username: 'testuser',
    email: 'test@example.com',
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('GET /api/projects', () => {
    it('should get projects for authenticated user', async () => {
      const mockProjects = [
        {
          id: 1,
          name: 'Project 1',
          description: 'First project',
          color: '#ff0000',
        },
        {
          id: 2,
          name: 'Project 2',
          description: 'Second project',
          color: '#00ff00',
        },
      ];

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.getProjects.mockResolvedValue(mockProjects);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
      };

      const response = await projectsGet({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData).toEqual(mockProjects);
      expect(TodoDB.getProjects).toHaveBeenCalledWith(1);
    });

    it('should return empty array when user has no projects', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.getProjects.mockResolvedValue([]);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
      };

      const response = await projectsGet({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(200);
      expect(responseData).toEqual([]);
      expect(TodoDB.getProjects).toHaveBeenCalledWith(1);
    });

    it('should return 401 for unauthenticated user', async () => {
      Auth.getSessionFromRequest.mockReturnValue('invalid-session');
      Auth.getSessionUser.mockResolvedValue(null);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=invalid-session') },
      };

      const response = await projectsGet({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Authentication required');
      expect(TodoDB.getProjects).not.toHaveBeenCalled();
    });

    it('should handle database errors', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.getProjects.mockRejectedValue(
        new Error('Database connection failed')
      );

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
      };

      const response = await projectsGet({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(500);
      expect(responseData.error).toBe('Database connection failed');
    });
  });

  describe('POST /api/projects', () => {
    it('should create new project successfully', async () => {
      const projectData = {
        name: 'New Project',
        description: 'Project description',
        color: '#3b82f6',
      };

      const createdProject = { id: 123 };

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.createProject.mockResolvedValue(createdProject);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue(projectData),
      };

      const response = await projectsPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(201);
      expect(responseData.id).toBe(123);
      expect(TodoDB.createProject).toHaveBeenCalledWith(
        1,
        'New Project',
        'Project description',
        '#3b82f6'
      );
    });

    it('should create project with default values', async () => {
      const projectData = {
        name: 'Simple Project',
        // description and color will use defaults
      };

      const createdProject = { id: 456 };

      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.createProject.mockResolvedValue(createdProject);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue(projectData),
      };

      const response = await projectsPost({ request });
      const body = await response.text();
      console.log(body);

      const responseData = JSON.parse(body);

      expect(response.status).toBe(201);
      expect(responseData.id).toBe(456);
      expect(TodoDB.createProject).toHaveBeenCalledWith(
        1,
        'Simple Project',
        undefined,
        undefined
      );
    });

    it('should return 401 for unauthenticated user', async () => {
      Auth.getSessionFromRequest.mockReturnValue(null);
      Auth.getSessionUser.mockResolvedValue(null);

      const request = {
        headers: { get: vi.fn().mockReturnValue(null) },
        json: vi.fn().mockResolvedValue({ name: 'Test Project' }),
      };

      const response = await projectsPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(401);
      expect(responseData.error).toBe('Authentication required');
      expect(TodoDB.createProject).not.toHaveBeenCalled();
    });

    it('should handle database errors during creation', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);
      TodoDB.createProject.mockRejectedValue(
        new Error('Duplicate project name')
      );

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockResolvedValue({ name: 'Duplicate Project' }),
      };

      const response = await projectsPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(500);
      expect(responseData.error).toBe('Duplicate project name');
    });

    it('should handle malformed JSON', async () => {
      Auth.getSessionFromRequest.mockReturnValue('session-123');
      Auth.getSessionUser.mockResolvedValue(mockSession);

      const request = {
        headers: { get: vi.fn().mockReturnValue('session=session-123') },
        json: vi.fn().mockRejectedValue(new Error('Invalid JSON')),
      };

      const response = await projectsPost({ request });
      const responseData = JSON.parse(await response.text());

      expect(response.status).toBe(500);
      expect(responseData.error).toBe('Invalid JSON');
      expect(TodoDB.createProject).not.toHaveBeenCalled();
    });
  });
});
