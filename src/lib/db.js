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
  CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    color TEXT DEFAULT '#3b82f6',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
  );

  CREATE TABLE IF NOT EXISTS todos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    FOREIGN KEY (project_id) REFERENCES projects (id)
  );

  CREATE INDEX IF NOT EXISTS idx_todos_project ON todos(project_id);
  CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
  CREATE INDEX IF NOT EXISTS idx_todos_priority ON todos(priority);
`);

export class TodoDB {
  // Project methods
  static getProjects() {
    try {
      return db.prepare('SELECT * FROM projects WHERE is_active = 1 ORDER BY name').all();
    } catch (error) {
      console.error('Error getting projects:', error);
      return [];
    }
  }

  static createProject(name, description = '', color = '#3b82f6') {
    return db.prepare('INSERT INTO projects (name, description, color) VALUES (?, ?, ?)').run(name, description, color);
  }

  static updateProject(id, updates) {
    const fields = Object.keys(updates).map(key => `${key} = ?`).join(', ');
    const values = [...Object.values(updates), id];
    return db.prepare(`UPDATE projects SET ${fields} WHERE id = ?`).run(...values);
  }

  // Todo methods
  static getTodos(projectId = null, status = null) {
    let query = `
      SELECT t.*, p.name as project_name, p.color as project_color 
      FROM todos t 
      LEFT JOIN projects p ON t.project_id = p.id 
      WHERE 1=1
    `;
    const params = [];

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

  static createTodo(todo) {
    const {
      project_id, title, description, priority, estimated_hours,
      due_date, tags, context
    } = todo;

    return db.prepare(`
      INSERT INTO todos (project_id, title, description, priority, estimated_hours, due_date, tags, context)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(project_id, title, description, priority, estimated_hours, due_date, JSON.stringify(tags || []), context);
  }

  static updateTodo(id, updates) {
    const fields = Object.keys(updates).map(key => `${key} = ?`).join(', ');
    const values = [...Object.values(updates), id];
    
    return db.prepare(`UPDATE todos SET ${fields}, updated_at = CURRENT_TIMESTAMP WHERE id = ?`).run(...values);
  }

  static completeTodo(id, actualHours) {
    return db.prepare(`
      UPDATE todos 
      SET status = 'completed', actual_hours = ?, completed_date = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
      WHERE id = ?
    `).run(actualHours, id);
  }

  static deleteTodo(id) {
    return db.prepare('DELETE FROM todos WHERE id = ?').run(id);
  }
}
