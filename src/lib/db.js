import pg from 'pg';
const { Pool } = pg;
import { config } from 'dotenv';

config();

const database_url =
  'postgresql://' +
  process.env.POSTGRES_USER +
  ':' +
  process.env.POSTGRES_PASSWORD +
  '@localhost:5432/' +
  process.env.POSTGRES_DB;
// Database connection
const pool = new Pool({
  connectionString: database_url,
});

export class TodoDB {
  static async query(text, params = []) {
    const client = await pool.connect();
    try {
      const result = await client.query(text, params);
      return result;
    } finally {
      client.release();
    }
  }

  // User methods
  static async createUser(username, email, passwordHash) {
    const result = await this.query(
      `
      INSERT INTO users (username, email, password_hash) VALUES ($1, $2, $3)
      RETURNING id
    `,
      [username, email, passwordHash]
    );
    return result.rows[0];
  }

  static async getUserByUsername(username) {
    const result = await this.query(
      `
      SELECT * FROM users WHERE username = $1 AND is_active = true
    `,
      [username]
    );
    return result.rows[0];
  }

  static async getUserByEmail(email) {
    const result = await this.query(
      `
      SELECT * FROM users WHERE email = $1 AND is_active = True
    `,
      [email]
    );
    return result.rows[0];
  }

  static async getUserById(id) {
    const result = await this.query(
      `
      SELECT * FROM users WHERE id = $1 AND is_active = True
    `,
      [id]
    );
    return result.rows[0];
  }

  // Session methods
  static async createSession(id, userId) {
    const result = await this.query(
      `
      INSERT INTO sessions (id, user_id, expires_at) VALUES ($1, $2, now() + interval '7' day)
      RETURNING id, expires_at
    `,
      [id, userId]
    );
    return result.rows[0];
  }

  static async getSession(sessionId) {
    const result = await this.query(
      `
      SELECT s.*, u.username, u.email 
      FROM sessions s 
      JOIN users u ON s.user_id = u.id 
      WHERE s.id = $1 AND s.expires_at > now() AND u.is_active = true
    `,
      [sessionId]
    );
    return result.rows[0];
  }

  static async deleteSession(sessionId) {
    const result = await this.query(
      `
    DELETE FROM sessions WHERE id = $1
    `,
      [sessionId]
    );
    return result.rows;
  }

  static async cleanupExpiredSessions() {
    const result = await this.query(`
      DELETE FROM sessions WHERE expires_at <= now()
    `);
    return result.rows;
  }

  // Project methods
  static async getProjects(user_id) {
    const result = await this.query(
      `
      SELECT * FROM projects 
      WHERE is_active = true
      AND user_id = $1
      ORDER BY name
    `,
      [user_id]
    );
    return result.rows;
  }

  static async createProject(
    user_id,
    name,
    description = '',
    color = '#3b82f6'
  ) {
    const result = await this.query(
      `
      INSERT INTO projects (user_id, name, description, color)
      VALUES ($1, $2, $3, $4)
      RETURNING id
    `,
      [user_id, name, description, color]
    );
    return result.rows[0];
  }

  static async updateProject(id, updates) {
    const fields = Object.keys(updates);
    const values = Object.values(updates);
    const setClause = fields
      .map((field, index) => `${field} = $${index + 1}`)
      .join(', ');

    const result = await this.query(
      `
      UPDATE projects 
      SET ${setClause}, updated_at = NOW()
      WHERE id = $${fields.length + 1}
      RETURNING *
    `,
      [...values, id]
    );

    return result.rows[0];
  }

  static async deleteProject(id) {
    // Soft delete - mark as inactive
    const result = await this.query(
      `
      UPDATE projects 
      SET is_active = false, updated_at = NOW()
      WHERE id = $1
      RETURNING *
    `,
      [id]
    );
    return result.rows[0];
  }

  // Todo methods
  static async getTodos(
    user_id,
    projectId = null,
    status = null,
    timeHorizon = null
  ) {
    let query = `
      SELECT t.*, p.name as project_name, p.color as project_color 
      FROM todos t 
      LEFT JOIN projects p ON t.project_id = p.id 
      WHERE t.user_id = $1
    `;
    const params = [user_id];
    let paramCount = 1;

    if (projectId) {
      paramCount++;
      query += ` AND t.project_id = $${paramCount}`;
      params.push(projectId);
    }
    if (status) {
      paramCount++;
      query += ` AND t.status = $${paramCount}`;
      params.push(status);
    }
    if (timeHorizon) {
      paramCount++;
      query += ` AND t.time_horizon = $${paramCount}`;
      params.push(timeHorizon);
    }

    query += ' ORDER BY t.priority DESC, t.created_at ASC';

    const result = await this.query(query, params);
    return result.rows;
  }

  static async createTodo(user_id, todo) {
    const {
      project_id,
      title,
      description,
      priority,
      estimated_hours,
      due_date,
      tags,
      context,
      time_horizon,
    } = todo;

    const result = await this.query(
      `
      INSERT INTO todos (project_id, user_id, title, description, priority, estimated_hours, due_date, tags, context, time_horizon)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
      RETURNING id
    `,
      [
        project_id,
        user_id,
        title,
        description,
        priority,
        estimated_hours,
        due_date,
        JSON.stringify(tags || []),
        context,
        time_horizon,
      ]
    );

    return result.rows[0];
  }

  static async updateTodo(id, user_id, updates) {
    const fields = Object.keys(updates);
    const values = Object.values(updates);
    const setClause = fields
      .map((field, index) => `${field} = $${index + 1}`)
      .join(', ');

    const result = await this.query(
      `
      UPDATE todos 
      SET ${setClause}, updated_at = NOW()
      WHERE id = $${fields.length + 1}
      RETURNING *
    `,
      [...values, id]
    );

    return result.rows[0];
  }

  static async completeTodo(id, user_id, actualHours) {
    const result = await this.query(
      `
      UPDATE todos 
      SET status = 'completed', actual_hours = $1, completed_date = NOW(), updated_at = NOW()
      WHERE id = $2
      RETURNING *
    `,
      [actualHours, id]
    );

    return result.rows[0];
  }

  static async deleteTodo(id) {
    const result = await this.query(
      `
      DELETE FROM todos WHERE id = $1 RETURNING *
    `,
      [id]
    );
    return result.rows[0];
  }

  // Analytics methods
  static async getCapacityStats(daysBack = 30) {
    const result = await this.query(`
      SELECT 
        DATE(completed_date) as date,
        SUM(actual_hours) as total_hours,
        COUNT(*) as tasks_completed
      FROM todos 
      WHERE status = 'completed' 
        AND completed_date >= NOW() - INTERVAL '${daysBack} days'
      GROUP BY DATE(completed_date)
      ORDER BY date
    `);
    return result.rows;
  }

  static async getEstimationAccuracy(daysBack = 90) {
    const result = await this.query(`
      SELECT 
        title,
        estimated_hours,
        actual_hours,
        priority,
        (actual_hours / estimated_hours) as accuracy_ratio,
        ABS(actual_hours - estimated_hours) as absolute_error
      FROM todos 
      WHERE status = 'completed' 
        AND completed_date >= NOW() - INTERVAL '${daysBack} days'
        AND estimated_hours > 0
      ORDER BY completed_date DESC
    `);
    return result.rows;
  }
}
