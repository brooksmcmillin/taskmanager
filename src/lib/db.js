import Database from 'better-sqlite3';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

let db;
try {
  db = new Database(join(process.cwd(), 'todos.db'));
} catch (error) {
  console.error('Database connection failed:', error);
  throw error;
}

// Initialize database
db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
  );

  CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    expires_at INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
  );

  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#3b82f6',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    UNIQUE(user_id, name)
  );

  CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    project_id INTEGER,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT CHECK(priority IN ('low', 'medium', 'high', 'urgent')) DEFAULT 'medium',
    estimated_hours REAL DEFAULT 1.0,
    actual_hours REAL,
    status TEXT CHECK(status IN ('pending', 'in_progress', 'completed', 'cancelled')) DEFAULT 'pending',
    due_date TEXT,
    completed_date TEXT,
    tags TEXT,
    context TEXT DEFAULT 'work',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects (id)
  );

  CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
  CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
  CREATE INDEX IF NOT EXISTS idx_projects_user ON projects(user_id);
  CREATE INDEX IF NOT EXISTS idx_todos_user ON todos(user_id);
  CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project_id);
  CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
  CREATE INDEX IF NOT EXISTS idx_todos_priority ON todos(priority);
`);

export class TodoDB {
  // User methods
  static createUser(username, email, passwordHash) {
    return db.prepare('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)').run(username, email, passwordHash);
  }

  static getUserByUsername(username) {
    return db.prepare('SELECT * FROM users WHERE username = ? AND is_active = 1').get(username);
  }

  static getUserByEmail(email) {
    return db.prepare('SELECT * FROM users WHERE email = ? AND is_active = 1').get(email);
  }

  static getUserById(id) {
    return db.prepare('SELECT * FROM users WHERE id = ? AND is_active = 1').get(id);
  }

  // Session methods
  static createSession(id, userId, expiresAt) {
    return db.prepare('INSERT INTO sessions (id, user_id, expires_at) VALUES (?, ?, ?)').run(id, userId, expiresAt);
  }

  static getSession(sessionId) {
    return db.prepare(`
      SELECT s.*, u.username, u.email 
      FROM sessions s 
      JOIN users u ON s.user_id = u.id 
      WHERE s.id = ? AND s.expires_at > ? AND u.is_active = 1
    `).get(sessionId, Date.now());
  }

  static deleteSession(sessionId) {
    return db.prepare('DELETE FROM sessions WHERE id = ?').run(sessionId);
  }

  static cleanupExpiredSessions() {
    return db.prepare('DELETE FROM sessions WHERE expires_at <= ?').run(Date.now());
  }

  // Project methods
  static getProjects(userId) {
    try {
      return db.prepare('SELECT * FROM projects WHERE user_id = ? AND is_active = 1 ORDER BY name').all(userId);
    } catch (error) {
      console.error('Error getting projects:', error);
      return [];
    }
  }

  static createProject(userId, name, description = '', color = '#3b82f6') {
    return db.prepare('INSERT INTO projects (user_id, name, description, color) VALUES (?, ?, ?, ?)').run(userId, name, description, color);
  }

  static updateProject(id, userId, updates) {
    const fields = Object.keys(updates).map(key => `${key} = ?`).join(', ');
    const values = [...Object.values(updates), id, userId];
    return db.prepare(`UPDATE projects SET ${fields} WHERE id = ? AND user_id = ?`).run(...values);
  }

  // Todo methods
  static getTodos(userId, projectId = null, status = null) {
    let query = `
      SELECT t.*, p.name as project_name, p.color as project_color 
      FROM todos t 
      LEFT JOIN projects p ON t.project_id = p.id 
      WHERE t.user_id = ?
    `;
    const params = [userId];

    if (projectId) {
      query += ' AND t.project_id = ?';
      params.push(projectId);
    }
    if (status) {
      query += ' AND t.status = ?';
      params.push(status);
    }

    query += ' ORDER BY t.priority DESC, t.created_at ASC';
    return db.prepare(query).all(...params);
  }

  static createTodo(userId, todo) {
    const {
      project_id, title, description, priority, estimated_hours,
      due_date, tags, context
    } = todo;

    return db.prepare(`
      INSERT INTO todos (user_id, project_id, title, description, priority, estimated_hours, due_date, tags, context)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `).run(userId, project_id, title, description, priority, estimated_hours, due_date, JSON.stringify(tags || []), context);
  }

  static updateTodo(id, userId, updates) {
    const fields = Object.keys(updates).map(key => `${key} = ?`).join(', ');
    const values = [...Object.values(updates), id, userId];
    
    return db.prepare(`UPDATE todos SET ${fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?`).run(...values);
  }

  static completeTodo(id, userId, actualHours) {
    return db.prepare(`
      UPDATE todos 
      SET status = 'completed', actual_hours = ?, completed_date = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
      WHERE id = ? AND user_id = ?
    `).run(actualHours, id, userId);
  }

  static deleteTodo(id, userId) {
    return db.prepare('DELETE FROM todos WHERE id = ? AND user_id = ?').run(id, userId);
  }
}
