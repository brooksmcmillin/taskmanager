import pg from 'pg';
import { config as dotenvConfig } from 'dotenv';
import crypto from 'crypto';
import bcrypt from 'bcryptjs';
import { CONFIG, config } from './config.js';

/**
 * SQL Query Builder utility
 * Provides a safe, fluent API for building parameterized SQL queries
 * Eliminates repetitive paramCount++ patterns and reduces SQL injection risk
 */

/**
 * @typedef {Object} QueryResult
 * @property {string} query - The SQL query string with placeholders
 * @property {Array} params - The parameter values
 */

// Regex patterns for validation
const VALID_FIELD_NAME = /^[a-zA-Z_][a-zA-Z0-9_.]*$/;
// Used for ORDER BY validation with bounded input; ReDoS risk is minimal
const VALID_ORDER_CLAUSE =
  /^[a-zA-Z_][a-zA-Z0-9_., ]*(ASC|DESC|asc|desc)?(\s*,\s*[a-zA-Z_][a-zA-Z0-9_., ]*(ASC|DESC|asc|desc)?)*$/; // eslint-disable-line security/detect-unsafe-regex

/**
 * Validate a field name to prevent SQL injection
 * @param {string} field - The field name to validate
 * @throws {Error} If field name is invalid
 */
function validateFieldName(field) {
  if (!VALID_FIELD_NAME.test(field)) {
    throw new Error(`Invalid field name: ${field}`);
  }
}

/**
 * Validate an ORDER BY clause to prevent SQL injection
 * @param {string} orderClause - The ORDER BY clause to validate
 * @throws {Error} If order clause is invalid
 */
function validateOrderClause(orderClause) {
  if (!VALID_ORDER_CLAUSE.test(orderClause)) {
    throw new Error(`Invalid ORDER BY clause: ${orderClause}`);
  }
}

class QueryBuilder {
  /**
   * Create a new QueryBuilder
   * @param {string} baseQuery - The base SELECT/UPDATE/DELETE query
   * @param {Array} initialParams - Initial parameters (default: [])
   */
  constructor(baseQuery, initialParams = []) {
    this.query = baseQuery;
    this.params = [...initialParams];
    this.paramCount = initialParams.length;
    this.hasWhere = baseQuery.toLowerCase().includes('where');
  }

  /**
   * Add a WHERE or AND condition based on whether WHERE exists
   * @param {string} condition - SQL condition with ? placeholder (e.g., "status = ?")
   * @param {*} value - The value to bind
   * @returns {QueryBuilder} this for chaining
   */
  where(condition, value) {
    if (value === null || value === undefined) {
      return this;
    }
    this.paramCount++;
    const keyword = this.hasWhere ? ' AND' : ' WHERE';
    this.query += `${keyword} ${condition.replace('?', `$${this.paramCount}`)}`;
    this.params.push(value);
    this.hasWhere = true;
    return this;
  }

  /**
   * Add a condition only if the value is truthy
   * @param {string} condition - SQL condition with ? placeholder
   * @param {*} value - The value to bind (condition added only if truthy)
   * @returns {QueryBuilder} this for chaining
   */
  whereIf(condition, value) {
    if (value) {
      return this.where(condition, value);
    }
    return this;
  }

  /**
   * Add a raw SQL fragment (no parameter binding)
   * WARNING: Only use with static SQL strings, never with user input!
   * @param {string} sql - Raw SQL to append (must be static/hardcoded)
   * @returns {QueryBuilder} this for chaining
   */
  whereRaw(sql) {
    // Development warning for potential misuse
    if (process.env.NODE_ENV !== 'production') {
      if (/\$\{|\$[a-zA-Z]|`/.test(sql)) {
        console.warn(
          '[QueryBuilder] whereRaw may contain template literal - potential SQL injection risk'
        );
      }
    }
    const keyword = this.hasWhere ? ' AND' : ' WHERE';
    this.query += `${keyword} ${sql}`;
    this.hasWhere = true;
    return this;
  }

  /**
   * Add a date range condition
   * @param {string} field - The date field name (must be valid SQL identifier)
   * @param {string|Date|null} startDate - Start date (inclusive)
   * @param {string|Date|null} endDate - End date (inclusive)
   * @returns {QueryBuilder} this for chaining
   * @throws {Error} If field name is invalid
   */
  whereDateRange(field, startDate, endDate) {
    validateFieldName(field);
    if (startDate) {
      this.where(`${field} >= ?`, startDate);
    }
    if (endDate) {
      this.where(`${field} <= ?`, endDate);
    }
    return this;
  }

  /**
   * Add an IN condition
   * @param {string} field - The field name (must be valid SQL identifier)
   * @param {Array} values - Array of values
   * @returns {QueryBuilder} this for chaining
   * @throws {Error} If field name is invalid
   */
  whereIn(field, values) {
    if (!values || values.length === 0) {
      return this;
    }
    validateFieldName(field);
    const placeholders = values.map(() => {
      this.paramCount++;
      return `$${this.paramCount}`;
    });
    const keyword = this.hasWhere ? ' AND' : ' WHERE';
    this.query += `${keyword} ${field} IN (${placeholders.join(', ')})`;
    this.params.push(...values);
    this.hasWhere = true;
    return this;
  }

  /**
   * Add ORDER BY clause
   * @param {string} orderClause - The order clause (e.g., "created_at DESC")
   * @returns {QueryBuilder} this for chaining
   * @throws {Error} If order clause contains invalid characters
   */
  orderBy(orderClause) {
    validateOrderClause(orderClause);
    this.query += ` ORDER BY ${orderClause}`;
    return this;
  }

  /**
   * Add LIMIT clause
   * @param {number|null} limit - The limit value
   * @returns {QueryBuilder} this for chaining
   */
  limit(limit) {
    if (limit && Number.isInteger(limit) && limit > 0) {
      this.paramCount++;
      this.query += ` LIMIT $${this.paramCount}`;
      this.params.push(limit);
    }
    return this;
  }

  /**
   * Add OFFSET clause
   * @param {number|null} offset - The offset value
   * @returns {QueryBuilder} this for chaining
   */
  offset(offset) {
    if (offset && Number.isInteger(offset) && offset >= 0) {
      this.paramCount++;
      this.query += ` OFFSET $${this.paramCount}`;
      this.params.push(offset);
    }
    return this;
  }

  /**
   * Build and return the query and params
   * @returns {QueryResult} Object with query string and params array
   */
  build() {
    return {
      query: this.query,
      params: this.params,
    };
  }

  /**
   * Get the current parameter count (useful for continuing manual building)
   * @returns {number}
   */
  getParamCount() {
    return this.paramCount;
  }
}

/**
 * Create a new QueryBuilder instance
 * @param {string} baseQuery - The base SQL query
 * @param {Array} initialParams - Initial parameters
 * @returns {QueryBuilder}
 */
export function createQuery(baseQuery, initialParams = []) {
  return new QueryBuilder(baseQuery, initialParams);
}

const { Pool } = pg;

dotenvConfig();

// Database connection - use lazy initialization to allow runtime env vars
let pool;
function getPool() {
  if (!pool) {
    // Use config getter to avoid Vite build-time optimization
    const database_url = config.database.connectionString;

    console.log('[DB] Creating pool with connection string:', database_url.replace(/:([^@]+)@/, ':***@'));
    console.log('[DB] ENV check - USER:', process.env['POSTGRES_USER'], 'DB:', process.env['POSTGRES_DB'], 'HOST:', process.env['POSTGRES_HOST']);

    pool = new Pool({
      connectionString: database_url,
    });
  }
  return pool;
}

export class TodoDB {
  static async query(text, params = []) {
    const client = await getPool().connect();
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

  static async getProjectById(id, user_id) {
    const result = await this.query(
      `
      SELECT * FROM projects
      WHERE id = $1 AND user_id = $2 AND is_active = true
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  /**
   * Get a project by name (case-insensitive)
   * @param {number} userId - User ID
   * @param {string} name - Project name to search for
   * @returns {Promise<Object|undefined>} Project or undefined if not found
   */
  static async getProjectByName(userId, name) {
    const result = await this.query(
      `
      SELECT * FROM projects
      WHERE user_id = $1 AND LOWER(name) = LOWER($2) AND is_active = true
    `,
      [userId, name]
    );
    return result.rows[0];
  }

  static async updateProject(id, user_id, updates) {
    // Whitelist allowed fields to prevent SQL injection via field names
    const allowedFields = ['name', 'description', 'color'];
    const fields = Object.keys(updates).filter((f) =>
      allowedFields.includes(f)
    );

    if (fields.length === 0) {
      throw new Error('No valid fields to update');
    }

    const values = fields.map((f) => updates[f]);
    const setClause = fields
      .map((field, index) => `${field} = $${index + 1}`)
      .join(', ');

    const result = await this.query(
      `
      UPDATE projects
      SET ${setClause}, updated_at = NOW()
      WHERE id = $${fields.length + 1} AND user_id = $${fields.length + 2}
      RETURNING *
    `,
      [...values, id, user_id]
    );

    return result.rows[0];
  }

  static async deleteProject(id, user_id) {
    // Soft delete - mark as inactive
    const result = await this.query(
      `
      UPDATE projects
      SET is_active = false, updated_at = NOW()
      WHERE id = $1 AND user_id = $2
      RETURNING *
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  static async getCategoriesWithCounts(user_id) {
    const result = await this.query(
      `
      SELECT
        p.name,
        COUNT(t.id) as task_count
      FROM projects p
      LEFT JOIN todos t ON p.id = t.project_id AND t.user_id = $1 AND t.deleted_at IS NULL
      WHERE p.is_active = true AND p.user_id = $1
      GROUP BY p.id, p.name
      ORDER BY p.name
    `,
      [user_id]
    );
    return result.rows;
  }

  // Todo methods
  static async getTodos(
    user_id,
    projectId = null,
    status = null,
    dueDate = null
  ) {
    const qb = createQuery(
      `SELECT t.*, p.name as project_name, p.color as project_color
       FROM todos t
       LEFT JOIN projects p ON t.project_id = p.id
       WHERE t.user_id = $1 AND t.deleted_at IS NULL`,
      [user_id]
    );

    qb.whereIf('t.project_id = ?', projectId)
      .whereIf('t.status = ?', status)
      .whereIf('t.due_date <= ?', dueDate)
      .orderBy('t.priority DESC, t.created_at ASC');

    const { query, params } = qb.build();
    const result = await this.query(query, params);
    return result.rows;
  }

  static async getTodosFiltered(user_id, options = {}) {
    const { projectId, category, status, startDate, endDate, limit } = options;

    const qb = createQuery(
      `SELECT t.*, p.name as project_name, p.color as project_color
       FROM todos t
       LEFT JOIN projects p ON t.project_id = p.id
       WHERE t.user_id = $1 AND t.deleted_at IS NULL`,
      [user_id]
    );

    // Filter by project/category (category maps to project name)
    if (projectId) {
      qb.where('t.project_id = ?', projectId);
    } else if (category) {
      qb.where('p.name = ?', category);
    }

    // Filter by status (handle 'overdue' as special case)
    if (status && status !== 'all') {
      if (status === 'overdue') {
        qb.whereRaw("t.status = 'pending' AND t.due_date < CURRENT_DATE");
      } else {
        qb.where('t.status = ?', status);
      }
    }

    // Filter by date range
    qb.whereDateRange('t.due_date', startDate, endDate)
      .orderBy('t.priority DESC, t.created_at ASC')
      .limit(limit);

    const { query, params } = qb.build();
    const result = await this.query(query, params);
    return result.rows;
  }

  static async getTodoById(id, user_id) {
    const result = await this.query(
      `
      SELECT
        t.*,
        p.name as project_name,
        p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.id = $1 AND t.user_id = $2 AND t.deleted_at IS NULL
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  static async getTodosForDateRange(
    user_id,
    startDate,
    endDate,
    status = null,
    strict
  ) {
    let query = `
      SELECT
        t.*,
        p.name as project_name,
        p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.user_id = $1 AND t.deleted_at IS NULL
    `;

    const params = [user_id];
    let paramIndex = 2;

    // Add date range filter
    if (startDate && endDate) {
      query += ` AND (
        (t.due_date IS NOT NULL`;

      query += ` AND t.due_date <= $${paramIndex + 1})
        OR (t.completed_date IS NOT NULL AND t.completed_date >= $${paramIndex} AND t.completed_date <= $${paramIndex + 1}::date + interval '1 day')
      )`;
      params.push(startDate, endDate);
      paramIndex += 2;
    }

    // Add status filter
    if (status) {
      query += ` AND t.status = $${paramIndex}`;
      params.push(status);
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
    } = todo;

    const result = await this.query(
      `
      INSERT INTO todos (project_id, user_id, title, description, priority, estimated_hours, due_date, tags, context)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
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
      ]
    );

    return result.rows[0];
  }

  static async updateTodo(id, user_id, updates) {
    // Whitelist allowed fields to prevent SQL injection via field names
    const allowedFields = [
      'project_id',
      'title',
      'description',
      'priority',
      'status',
      'estimated_hours',
      'actual_hours',
      'due_date',
      'completed_date',
      'tags',
      'context',
    ];
    const fields = Object.keys(updates).filter((f) =>
      allowedFields.includes(f)
    );

    if (fields.length === 0) {
      throw new Error('No valid fields to update');
    }

    const values = fields.map((f) => {
      // Tags need to be JSON stringified for PostgreSQL
      if (f === 'tags') {
        return JSON.stringify(updates[f] || []);
      }
      return updates[f];
    });
    const setClause = fields
      .map((field, index) => `${field} = $${index + 1}`)
      .join(', ');

    const result = await this.query(
      `
      UPDATE todos
      SET ${setClause}, updated_at = NOW()
      WHERE id = $${fields.length + 1} AND user_id = $${fields.length + 2}
      RETURNING *
    `,
      [...values, id, user_id]
    );

    return result.rows[0];
  }

  static async completeTodo(id, user_id) {
    const result = await this.query(
      `
      UPDATE todos
      SET status = 'completed', completed_date = NOW(), updated_at = NOW()
      WHERE id = $1 AND user_id = $2
      RETURNING *
    `,
      [id, user_id]
    );

    return result.rows[0];
  }

  static async deleteTodo(id, user_id) {
    // Soft delete - set deleted_at timestamp
    const result = await this.query(
      `
      UPDATE todos
      SET deleted_at = NOW(), updated_at = NOW()
      WHERE id = $1 AND user_id = $2 AND deleted_at IS NULL
      RETURNING *
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  // Trash/deleted todos methods
  static async getDeletedTodos(user_id) {
    const result = await this.query(
      `
      SELECT t.*, p.name as project_name, p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.user_id = $1 AND t.deleted_at IS NOT NULL
      ORDER BY t.deleted_at DESC
    `,
      [user_id]
    );
    return result.rows;
  }

  static async getDeletedTodoById(id, user_id) {
    const result = await this.query(
      `
      SELECT t.*, p.name as project_name, p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.id = $1 AND t.user_id = $2 AND t.deleted_at IS NOT NULL
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  static async searchDeletedTodos(user_id, searchQuery) {
    const result = await this.query(
      `
      SELECT t.*, p.name as project_name, p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.user_id = $1 AND t.deleted_at IS NOT NULL
        AND to_tsvector('english', t.title || ' ' || COALESCE(t.description, '')) @@ plainto_tsquery('english', $2)
      ORDER BY t.deleted_at DESC
    `,
      [user_id, searchQuery]
    );
    return result.rows;
  }

  static async restoreTodo(id, user_id) {
    const result = await this.query(
      `
      UPDATE todos
      SET deleted_at = NULL, updated_at = NOW()
      WHERE id = $1 AND user_id = $2 AND deleted_at IS NOT NULL
      RETURNING *
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  static async permanentlyDeleteTodo(id, user_id) {
    const result = await this.query(
      `
      DELETE FROM todos
      WHERE id = $1 AND user_id = $2 AND deleted_at IS NOT NULL
      RETURNING *
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  static async searchTodos(user_id, searchQuery, category = null) {
    const qb = createQuery(
      `SELECT t.*, p.name as project_name, p.color as project_color
       FROM todos t
       LEFT JOIN projects p ON t.project_id = p.id
       WHERE t.user_id = $1 AND t.deleted_at IS NULL
         AND to_tsvector('english', t.title || ' ' || COALESCE(t.description, '')) @@ plainto_tsquery('english', $2)`,
      [user_id, searchQuery]
    );

    qb.whereIf('p.name = ?', category).orderBy(
      't.priority DESC, t.created_at ASC'
    );

    const { query, params } = qb.build();
    const result = await this.query(query, params);
    return result.rows;
  }

  // Recurring Task methods

  /**
   * Calculate the next due date based on recurrence pattern
   * @param {Object} recurringTask - The recurring task
   * @param {Date|string} fromDate - The reference date to calculate from
   * @returns {Date|null} The next due date, or null if past end_date
   */
  static calculateNextDueDate(recurringTask, fromDate) {
    const from = new Date(fromDate);
    const { frequency, interval_value, weekdays, day_of_month, end_date } =
      recurringTask;

    let next = new Date(from);

    switch (frequency) {
      case 'daily':
        next.setDate(next.getDate() + interval_value);
        break;

      case 'weekly':
        if (weekdays && weekdays.length > 0) {
          // Find the next matching weekday
          const sortedDays = [...weekdays].sort((a, b) => a - b);
          const currentDay = next.getDay();

          // Look for next day this week
          let foundThisWeek = false;
          for (const day of sortedDays) {
            if (day > currentDay) {
              next.setDate(next.getDate() + (day - currentDay));
              foundThisWeek = true;
              break;
            }
          }

          // If not found this week, go to first day of next interval
          if (!foundThisWeek) {
            const daysUntilNextWeek = 7 - currentDay + sortedDays[0];
            const additionalWeeks = (interval_value - 1) * 7;
            next.setDate(next.getDate() + daysUntilNextWeek + additionalWeeks);
          }
        } else {
          // Simple weekly: same day next week(s)
          next.setDate(next.getDate() + 7 * interval_value);
        }
        break;

      case 'monthly':
        next.setMonth(next.getMonth() + interval_value);
        if (day_of_month) {
          // Handle months with fewer days (e.g., Feb 30 -> Feb 28)
          const lastDay = new Date(
            next.getFullYear(),
            next.getMonth() + 1,
            0
          ).getDate();
          next.setDate(Math.min(day_of_month, lastDay));
        }
        break;

      case 'yearly':
        next.setFullYear(next.getFullYear() + interval_value);
        break;
    }

    // Check if past end_date
    if (end_date && next > new Date(end_date)) {
      return null;
    }

    return next;
  }

  /**
   * Create a new recurring task
   * @param {number} user_id - User ID
   * @param {Object} task - Recurring task data
   * @returns {Object} Created recurring task
   */
  static async createRecurringTask(user_id, task) {
    const {
      frequency,
      interval_value = 1,
      weekdays = null,
      day_of_month = null,
      start_date,
      end_date = null,
      project_id = null,
      title,
      description = null,
      priority = 'medium',
      estimated_hours = 1.0,
      tags = [],
      context = 'work',
      skip_missed = true,
    } = task;

    // Calculate initial next_due_date based on start_date and pattern
    let next_due_date = new Date(start_date);

    // For weekly tasks with specific weekdays, find the first matching day
    // on or after start_date
    if (frequency === 'weekly' && weekdays && weekdays.length > 0) {
      const startDay = next_due_date.getDay();
      const sortedDays = [...weekdays].sort((a, b) => a - b);

      // Find first matching day on or after start
      let foundDay = false;
      for (const day of sortedDays) {
        if (day >= startDay) {
          next_due_date.setDate(next_due_date.getDate() + (day - startDay));
          foundDay = true;
          break;
        }
      }
      if (!foundDay) {
        // Wrap to next week
        const daysUntilNextWeek = 7 - startDay + sortedDays[0];
        next_due_date.setDate(next_due_date.getDate() + daysUntilNextWeek);
      }
    }

    const result = await this.query(
      `
      INSERT INTO recurring_tasks (
        user_id, frequency, interval_value, weekdays, day_of_month,
        start_date, end_date, next_due_date, project_id, title,
        description, priority, estimated_hours, tags, context, skip_missed
      ) VALUES (
        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
      )
      RETURNING *
      `,
      [
        user_id,
        frequency,
        interval_value,
        weekdays,
        day_of_month,
        start_date,
        end_date,
        next_due_date.toISOString().split('T')[0],
        project_id,
        title,
        description,
        priority,
        estimated_hours,
        JSON.stringify(tags),
        context,
        skip_missed,
      ]
    );

    return result.rows[0];
  }

  /**
   * Get all recurring tasks for a user
   * @param {number} user_id - User ID
   * @param {boolean} activeOnly - Only return active recurring tasks
   * @returns {Array} Recurring tasks
   */
  static async getRecurringTasks(user_id, activeOnly = true) {
    const qb = createQuery(
      `SELECT rt.*, p.name as project_name, p.color as project_color
       FROM recurring_tasks rt
       LEFT JOIN projects p ON rt.project_id = p.id
       WHERE rt.user_id = $1`,
      [user_id]
    );

    if (activeOnly) {
      qb.whereRaw('rt.is_active = true');
    }

    qb.orderBy('rt.next_due_date ASC, rt.created_at ASC');

    const { query, params } = qb.build();
    const result = await this.query(query, params);
    return result.rows;
  }

  /**
   * Get a single recurring task by ID
   * @param {number} id - Recurring task ID
   * @param {number} user_id - User ID
   * @returns {Object|null} Recurring task or null
   */
  static async getRecurringTaskById(id, user_id) {
    const result = await this.query(
      `
      SELECT rt.*, p.name as project_name, p.color as project_color
      FROM recurring_tasks rt
      LEFT JOIN projects p ON rt.project_id = p.id
      WHERE rt.id = $1 AND rt.user_id = $2
      `,
      [id, user_id]
    );
    return result.rows[0] || null;
  }

  /**
   * Update a recurring task
   * @param {number} id - Recurring task ID
   * @param {number} user_id - User ID
   * @param {Object} updates - Fields to update
   * @returns {Object|null} Updated recurring task
   */
  static async updateRecurringTask(id, user_id, updates) {
    const allowedFields = [
      'frequency',
      'interval_value',
      'weekdays',
      'day_of_month',
      'start_date',
      'end_date',
      'next_due_date',
      'project_id',
      'title',
      'description',
      'priority',
      'estimated_hours',
      'tags',
      'context',
      'skip_missed',
      'is_active',
    ];

    const fields = Object.keys(updates).filter((f) =>
      allowedFields.includes(f)
    );

    if (fields.length === 0) {
      throw new Error('No valid fields to update');
    }

    const values = fields.map((f) => {
      if (f === 'tags') return JSON.stringify(updates[f]);
      return updates[f];
    });

    const setClause = fields
      .map((field, index) => `${field} = $${index + 1}`)
      .join(', ');

    const result = await this.query(
      `
      UPDATE recurring_tasks
      SET ${setClause}, updated_at = NOW()
      WHERE id = $${fields.length + 1} AND user_id = $${fields.length + 2}
      RETURNING *
      `,
      [...values, id, user_id]
    );

    return result.rows[0] || null;
  }

  /**
   * Deactivate a recurring task (soft delete)
   * @param {number} id - Recurring task ID
   * @param {number} user_id - User ID
   * @returns {Object|null} Deactivated recurring task
   */
  static async deleteRecurringTask(id, user_id) {
    const result = await this.query(
      `
      UPDATE recurring_tasks
      SET is_active = false, updated_at = NOW()
      WHERE id = $1 AND user_id = $2
      RETURNING *
      `,
      [id, user_id]
    );
    return result.rows[0] || null;
  }

  /**
   * Generate todos for recurring tasks that are due
   * Called on-demand when fetching tasks
   * @param {number} user_id - User ID
   * @returns {Array} Generated todos
   */
  static async generateDueRecurringTasks(user_id) {
    const today = new Date().toISOString().split('T')[0];

    // Find recurring tasks that need generation (next_due_date <= today)
    const dueRecurring = await this.query(
      `
      SELECT * FROM recurring_tasks
      WHERE user_id = $1
        AND is_active = true
        AND next_due_date <= $2
        AND (end_date IS NULL OR end_date >= $2)
      `,
      [user_id, today]
    );

    const generatedTodos = [];

    for (const recurring of dueRecurring.rows) {
      // Check if a todo for this occurrence already exists
      const existing = await this.query(
        `
        SELECT id FROM todos
        WHERE recurring_task_id = $1 AND due_date = $2
        `,
        [recurring.id, recurring.next_due_date]
      );

      if (existing.rows.length === 0) {
        // Create the todo
        const todoResult = await this.query(
          `
          INSERT INTO todos (
            user_id, project_id, title, description, priority,
            estimated_hours, due_date, tags, context, recurring_task_id
          ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
          RETURNING *
          `,
          [
            user_id,
            recurring.project_id,
            recurring.title,
            recurring.description,
            recurring.priority,
            recurring.estimated_hours,
            recurring.next_due_date,
            recurring.tags,
            recurring.context,
            recurring.id,
          ]
        );
        generatedTodos.push(todoResult.rows[0]);
      }

      // Calculate and update the next due date
      const nextDate = this.calculateNextDueDate(
        recurring,
        recurring.next_due_date
      );

      if (nextDate) {
        await this.query(
          `
          UPDATE recurring_tasks
          SET next_due_date = $1, updated_at = NOW()
          WHERE id = $2
          `,
          [nextDate.toISOString().split('T')[0], recurring.id]
        );
      } else {
        // No more occurrences (past end_date), deactivate
        await this.query(
          `
          UPDATE recurring_tasks
          SET is_active = false, updated_at = NOW()
          WHERE id = $1
          `,
          [recurring.id]
        );
      }
    }

    return generatedTodos;
  }

  /**
   * Complete a recurring todo with proper recurrence handling
   * If skip_missed is true (floating), recalculates next_due_date from today
   * @param {number} id - Todo ID
   * @param {number} user_id - User ID
   * @returns {Object} Completed todo and optionally next occurrence info
   */
  static async completeRecurringTodo(id, user_id) {
    // Get the todo to check if it's recurring
    const todo = await this.getTodoById(id, user_id);
    if (!todo) {
      return null;
    }

    // Mark as complete
    const completed = await this.completeTodo(id, user_id);

    // If not a recurring task, just return the completed todo
    if (!todo.recurring_task_id) {
      return { todo: completed, recurring: null };
    }

    // Get the recurring task
    const recurring = await this.getRecurringTaskById(
      todo.recurring_task_id,
      user_id
    );

    if (!recurring || !recurring.is_active) {
      return { todo: completed, recurring: null };
    }

    // If skip_missed is true (floating), recalculate from today
    if (recurring.skip_missed) {
      const today = new Date();
      const nextDate = this.calculateNextDueDate(recurring, today);

      if (nextDate) {
        await this.query(
          `
          UPDATE recurring_tasks
          SET next_due_date = $1, updated_at = NOW()
          WHERE id = $2
          `,
          [nextDate.toISOString().split('T')[0], recurring.id]
        );
        return {
          todo: completed,
          recurring: { next_due_date: nextDate.toISOString().split('T')[0] },
        };
      }
    }

    return { todo: completed, recurring };
  }

  // Analytics methods
  static async getCapacityStats(daysBack = 30) {
    // Validate and sanitize daysBack to prevent SQL injection
    const days = parseInt(daysBack, 10);
    if (isNaN(days) || days < 1 || days > 365) {
      throw new Error('Invalid daysBack parameter: must be between 1 and 365');
    }

    const result = await this.query(
      `
      SELECT
        DATE(completed_date) as date,
        SUM(actual_hours) as total_hours,
        COUNT(*) as tasks_completed
      FROM todos
      WHERE status = 'completed'
        AND completed_date >= NOW() - INTERVAL '1 day' * $1
      GROUP BY DATE(completed_date)
      ORDER BY date
    `,
      [days]
    );
    return result.rows;
  }

  static async getEstimationAccuracy(daysBack = 90) {
    // Validate and sanitize daysBack to prevent SQL injection
    const days = parseInt(daysBack, 10);
    if (isNaN(days) || days < 1 || days > 365) {
      throw new Error('Invalid daysBack parameter: must be between 1 and 365');
    }

    const result = await this.query(
      `
      SELECT
        title,
        estimated_hours,
        actual_hours,
        priority,
        (actual_hours / estimated_hours) as accuracy_ratio,
        ABS(actual_hours - estimated_hours) as absolute_error
      FROM todos
      WHERE status = 'completed'
        AND completed_date >= NOW() - INTERVAL '1 day' * $1
        AND estimated_hours > 0
      ORDER BY completed_date DESC
    `,
      [days]
    );
    return result.rows;
  }

  // API Key methods
  static async createApiKey(userId, apiKey) {
    const hashedKey = await bcrypt.hash(apiKey, CONFIG.BCRYPT_ROUNDS);
    const result = await this.query(
      `
      INSERT INTO api_keys (user_id, key_hash, created_at)
      VALUES ($1, $2, NOW())
      RETURNING id
    `,
      [userId, hashedKey]
    );
    return result.rows[0];
  }

  static async getUserByApiKey(apiKey) {
    // Get all active API keys for comparison with bcrypt
    const result = await this.query(
      `
      SELECT u.*, ak.id as api_key_id, ak.key_hash
      FROM users u
      JOIN api_keys ak ON u.id = ak.user_id
      WHERE ak.is_active = true AND u.is_active = true
    `
    );

    // Use bcrypt.compare to check each hash
    for (const row of result.rows) {
      const match = await bcrypt.compare(apiKey, row.key_hash);
      if (match) {
        // Remove key_hash from returned object for security
        delete row.key_hash;
        return row;
      }
    }

    return null;
  }

  static async revokeApiKey(userId, apiKey) {
    // Get all active keys for this user
    const keys = await this.query(
      `
      SELECT id, key_hash
      FROM api_keys
      WHERE user_id = $1 AND is_active = true
    `,
      [userId]
    );

    // Find the matching key using bcrypt
    for (const key of keys.rows) {
      const match = await bcrypt.compare(apiKey, key.key_hash);
      if (match) {
        const result = await this.query(
          `
          UPDATE api_keys
          SET is_active = false
          WHERE id = $1
          RETURNING id
        `,
          [key.id]
        );
        return result.rows[0];
      }
    }

    return null;
  }

  static async getUserApiKeys(userId) {
    const result = await this.query(
      `
      SELECT id, name, created_at, is_active
      FROM api_keys
      WHERE user_id = $1
      ORDER BY created_at DESC
    `,
      [userId]
    );
    return result.rows;
  }

  // OAuth methods
  /**
   * Create a new OAuth client
   * @param {string} clientId - Unique client identifier
   * @param {string|null} clientSecret - Client secret (null for public clients)
   * @param {string} name - Human-readable client name
   * @param {string[]} redirectUris - Allowed redirect URIs
   * @param {string[]} grantTypes - Allowed grant types
   * @param {string[]} scopes - Allowed scopes
   * @param {number|null} userId - Owner user ID
   * @param {boolean} isPublic - True for public clients (RFC 6749 Section 2.1)
   * @returns {Object} Created client record
   */
  static async createOAuthClient(
    clientId,
    clientSecret,
    name,
    redirectUris,
    grantTypes = ['authorization_code'],
    scopes = ['read'],
    userId = null,
    isPublic = false
  ) {
    // Public clients (native apps, SPAs, devices) don't use client_secret
    const hashedSecret = isPublic
      ? null
      : await bcrypt.hash(clientSecret, CONFIG.BCRYPT_ROUNDS);

    const result = await this.query(
      `
      INSERT INTO oauth_clients (client_id, client_secret_hash, name, redirect_uris, grant_types, scopes, user_id, is_public, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
      RETURNING id, client_id, name, redirect_uris, user_id, is_public
    `,
      [
        clientId,
        hashedSecret,
        name,
        JSON.stringify(redirectUris),
        JSON.stringify(grantTypes),
        JSON.stringify(scopes),
        userId,
        isPublic,
      ]
    );
    return result.rows[0];
  }

  static async getOAuthClient(clientId) {
    const result = await this.query(
      `
      SELECT id, client_id, name, redirect_uris, grant_types, scopes, is_active, is_public
      FROM oauth_clients
      WHERE client_id = $1 AND is_active = true
    `,
      [clientId]
    );
    return result.rows[0];
  }

  static async validateOAuthClient(clientId, clientSecret) {
    // First get the client by ID
    const result = await this.query(
      `
      SELECT id, client_id, name, redirect_uris, grant_types, scopes, client_secret_hash, user_id, is_public
      FROM oauth_clients
      WHERE client_id = $1 AND is_active = true
    `,
      [clientId]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const client = result.rows[0];

    // Check if this is a public client using the database field (RFC 6749 Section 2.1)
    // Public clients (native apps, SPAs) don't require client_secret
    if (client.is_public === true) {
      delete client.client_secret_hash;
      return client;
    }

    // For confidential clients, validate the secret
    if (!clientSecret) {
      return null;
    }

    // Use bcrypt to compare the provided secret with the stored hash
    const match = await bcrypt.compare(clientSecret, client.client_secret_hash);

    if (!match) {
      return null;
    }

    // Remove the hash from the returned object for security
    delete client.client_secret_hash;
    return client;
  }

  static async createAuthorizationCode(
    clientId,
    userId,
    redirectUri,
    scopes,
    codeChallenge = null,
    codeChallengeMethod = null
  ) {
    const code = crypto.randomBytes(32).toString('hex');
    const result = await this.query(
      `
      INSERT INTO authorization_codes (code, client_id, user_id, redirect_uri, scopes, code_challenge, code_challenge_method, expires_at, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, NOW() + INTERVAL '10 minutes', NOW())
      RETURNING code
    `,
      [
        code,
        clientId,
        userId,
        redirectUri,
        JSON.stringify(scopes),
        codeChallenge,
        codeChallengeMethod,
      ]
    );
    return result.rows[0];
  }

  static async consumeAuthorizationCode(code, clientId) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      const result = await client.query(
        `
        SELECT ac.*, u.id as user_id, u.username
        FROM authorization_codes ac
        JOIN users u ON ac.user_id = u.id
        WHERE ac.code = $1 AND ac.client_id = $2 AND ac.expires_at > NOW() AND ac.used = false
      `,
        [code, clientId]
      );

      if (result.rows.length === 0) {
        await client.query('ROLLBACK');
        return null;
      }

      await client.query(
        'UPDATE authorization_codes SET used = true WHERE code = $1',
        [code]
      );

      await client.query('COMMIT');
      return result.rows[0];
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  static async createAccessToken(userId, clientId, scopes, expiresIn = 3600) {
    const token = crypto.randomBytes(32).toString('hex');
    const refreshToken = crypto.randomBytes(32).toString('hex');
    const expiresAt = new Date(Date.now() + expiresIn * 1000);

    const result = await this.query(
      `
      INSERT INTO access_tokens (token, refresh_token, user_id, client_id, scopes, expires_at, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, NOW())
      RETURNING token, refresh_token
    `,
      [token, refreshToken, userId, clientId, JSON.stringify(scopes), expiresAt]
    );
    return result.rows[0];
  }

  static async getAccessToken(token) {
    const result = await this.query(
      `
      SELECT at.*, u.id as user_id, u.username, oc.client_id
      FROM access_tokens at
      JOIN users u ON at.user_id = u.id
      JOIN oauth_clients oc ON at.client_id = oc.client_id
      WHERE at.token = $1 AND at.expires_at > NOW() AND at.revoked = false
    `,
      [token]
    );
    return result.rows[0];
  }

  static async refreshAccessToken(refreshToken, clientId) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      const result = await client.query(
        `
        SELECT at.*, u.id as user_id
        FROM access_tokens at
        JOIN users u ON at.user_id = u.id
        WHERE at.refresh_token = $1 AND at.client_id = $2 AND at.revoked = false
      `,
        [refreshToken, clientId]
      );

      if (result.rows.length === 0) {
        await client.query('ROLLBACK');
        return null;
      }

      const oldToken = result.rows[0];

      await client.query(
        'UPDATE access_tokens SET revoked = true WHERE refresh_token = $1',
        [refreshToken]
      );

      const newToken = crypto.randomBytes(32).toString('hex');
      const newRefreshToken = crypto.randomBytes(32).toString('hex');
      const expiresAt = new Date(Date.now() + 3600 * 1000);

      const newTokenResult = await client.query(
        `
        INSERT INTO access_tokens (token, refresh_token, user_id, client_id, scopes, expires_at, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, NOW())
        RETURNING token, refresh_token
      `,
        [
          newToken,
          newRefreshToken,
          oldToken.user_id,
          clientId,
          oldToken.scopes,
          expiresAt,
        ]
      );

      await client.query('COMMIT');
      return newTokenResult.rows[0];
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  // Device Authorization Grant (RFC 8628) methods

  /**
   * Generate a user-friendly code (e.g., WDJB-MJHT)
   * Uses characters that are unambiguous (no 0/O, 1/I/L confusion)
   */
  static generateUserCode() {
    const chars = 'BCDFGHJKLMNPQRSTVWXZ'; // Consonants only, no ambiguous chars
    let code = '';
    for (let i = 0; i < 8; i++) {
      if (i === 4) code += '-'; // Add hyphen in middle
      code += chars[crypto.randomInt(chars.length)];
    }
    return code;
  }

  /**
   * Create a device authorization code for the Device Flow
   * @param {string} clientId - OAuth client ID
   * @param {string[]} scopes - Requested scopes
   * @param {number} expiresIn - Expiration in seconds (default 1800 = 30 minutes)
   * @param {number} interval - Polling interval in seconds (default 5)
   * @returns {Object} Device code data including device_code, user_code, etc.
   */
  static async createDeviceAuthorizationCode(
    clientId,
    scopes,
    expiresIn = 1800,
    interval = 5
  ) {
    const deviceCode = crypto.randomBytes(32).toString('hex');
    let userCode;
    let attempts = 0;
    const maxAttempts = 10;

    // Generate unique user code with retry logic
    while (attempts < maxAttempts) {
      userCode = this.generateUserCode();
      try {
        const expiresAt = new Date(Date.now() + expiresIn * 1000);
        const result = await this.query(
          `
          INSERT INTO device_authorization_codes
            (device_code, user_code, client_id, scopes, status, expires_at, interval, created_at)
          VALUES ($1, $2, $3, $4, 'pending', $5, $6, NOW())
          RETURNING device_code, user_code, expires_at, interval
          `,
          [
            deviceCode,
            userCode,
            clientId,
            JSON.stringify(scopes),
            expiresAt,
            interval,
          ]
        );
        return {
          ...result.rows[0],
          expires_in: expiresIn,
        };
      } catch (error) {
        // If unique constraint violation on user_code, retry
        if (error.code === '23505' && error.constraint?.includes('user_code')) {
          attempts++;
          continue;
        }
        throw error;
      }
    }
    throw new Error('Failed to generate unique user code after max attempts');
  }

  /**
   * Get device authorization by user code (for user verification page)
   * @param {string} userCode - The user-facing code (e.g., WDJB-MJHT)
   * @returns {Object|null} Device authorization data or null if not found/expired
   */
  static async getDeviceAuthorizationByUserCode(userCode) {
    // Normalize user code: uppercase and remove any spaces/hyphens for matching
    const normalizedCode = userCode.toUpperCase().replace(/[\s-]/g, '');
    const formattedCode =
      normalizedCode.slice(0, 4) + '-' + normalizedCode.slice(4);

    const result = await this.query(
      `
      SELECT dac.*, oc.name as client_name
      FROM device_authorization_codes dac
      JOIN oauth_clients oc ON dac.client_id = oc.client_id
      WHERE dac.user_code = $1
        AND dac.expires_at > NOW()
        AND dac.status = 'pending'
      `,
      [formattedCode]
    );
    return result.rows[0] || null;
  }

  /**
   * Get device authorization by device code (for token endpoint polling)
   * @param {string} deviceCode - The device code (secret)
   * @param {string} clientId - OAuth client ID
   * @returns {Object|null} Device authorization data with polling info
   */
  static async getDeviceAuthorizationByDeviceCode(deviceCode, clientId) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      const result = await client.query(
        `
        SELECT dac.*, u.username
        FROM device_authorization_codes dac
        LEFT JOIN users u ON dac.user_id = u.id
        WHERE dac.device_code = $1 AND dac.client_id = $2
        FOR UPDATE OF dac
        `,
        [deviceCode, clientId]
      );

      if (result.rows.length === 0) {
        await client.query('ROLLBACK');
        return null;
      }

      const deviceAuth = result.rows[0];
      const now = new Date();

      // Check rate limiting (slow_down if polling too fast)
      if (deviceAuth.last_poll_at) {
        const timeSinceLastPoll =
          (now - new Date(deviceAuth.last_poll_at)) / 1000;
        if (timeSinceLastPoll < deviceAuth.interval) {
          // Update last_poll_at and increase interval
          await client.query(
            `
            UPDATE device_authorization_codes
            SET last_poll_at = NOW(), interval = interval + 5
            WHERE device_code = $1
            `,
            [deviceCode]
          );
          await client.query('COMMIT');
          return { ...deviceAuth, slow_down: true };
        }
      }

      // Update last_poll_at
      await client.query(
        `
        UPDATE device_authorization_codes
        SET last_poll_at = NOW()
        WHERE device_code = $1
        `,
        [deviceCode]
      );

      await client.query('COMMIT');
      return deviceAuth;
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Authorize a device code (called when user approves)
   * @param {string} userCode - The user-facing code
   * @param {number} userId - The authorizing user's ID
   * @returns {Object|null} Updated device authorization or null if not found
   */
  static async authorizeDeviceCode(userCode, userId) {
    const normalizedCode = userCode.toUpperCase().replace(/[\s-]/g, '');
    const formattedCode =
      normalizedCode.slice(0, 4) + '-' + normalizedCode.slice(4);

    const result = await this.query(
      `
      UPDATE device_authorization_codes
      SET status = 'authorized', user_id = $2
      WHERE user_code = $1
        AND expires_at > NOW()
        AND status = 'pending'
      RETURNING *
      `,
      [formattedCode, userId]
    );
    return result.rows[0] || null;
  }

  /**
   * Deny a device code (called when user rejects)
   * @param {string} userCode - The user-facing code
   * @returns {Object|null} Updated device authorization or null if not found
   */
  static async denyDeviceCode(userCode) {
    const normalizedCode = userCode.toUpperCase().replace(/[\s-]/g, '');
    const formattedCode =
      normalizedCode.slice(0, 4) + '-' + normalizedCode.slice(4);

    const result = await this.query(
      `
      UPDATE device_authorization_codes
      SET status = 'denied'
      WHERE user_code = $1
        AND expires_at > NOW()
        AND status = 'pending'
      RETURNING *
      `,
      [formattedCode]
    );
    return result.rows[0] || null;
  }

  /**
   * Consume a device authorization code (mark as used after token issued)
   * @param {string} deviceCode - The device code
   * @returns {Object|null} Device authorization data or null
   */
  static async consumeDeviceAuthorizationCode(deviceCode) {
    const client = await pool.connect();
    try {
      await client.query('BEGIN');

      const result = await client.query(
        `
        SELECT dac.*, u.id as user_id
        FROM device_authorization_codes dac
        JOIN users u ON dac.user_id = u.id
        WHERE dac.device_code = $1
          AND dac.status = 'authorized'
          AND dac.expires_at > NOW()
        FOR UPDATE OF dac
        `,
        [deviceCode]
      );

      if (result.rows.length === 0) {
        await client.query('ROLLBACK');
        return null;
      }

      // Mark as consumed by changing status
      await client.query(
        `
        UPDATE device_authorization_codes
        SET status = 'consumed'
        WHERE device_code = $1
        `,
        [deviceCode]
      );

      await client.query('COMMIT');
      return result.rows[0];
    } catch (error) {
      await client.query('ROLLBACK');
      throw error;
    } finally {
      client.release();
    }
  }

  /**
   * Cleanup expired device authorization codes
   * @returns {number} Number of rows deleted
   */
  static async cleanupExpiredDeviceAuthorizationCodes() {
    const result = await this.query(`
      DELETE FROM device_authorization_codes
      WHERE expires_at <= NOW() OR status IN ('consumed', 'denied')
    `);
    return result.rowCount;
  }
}
