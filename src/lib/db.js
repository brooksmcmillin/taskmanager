import pg from 'pg';
const { Pool } = pg;
import { config } from 'dotenv';
import crypto from 'crypto';
import bcrypt from 'bcrypt';

config();

const database_url =
  'postgresql://' +
  process.env.POSTGRES_USER +
  ':' +
  process.env.POSTGRES_PASSWORD +
  '@' +
  (process.env.POSTGRES_HOST || 'localhost') +
  ':5432/' +
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

  static async updateProject(id, user_id, updates) {
    // Whitelist allowed fields to prevent SQL injection via field names
    const allowedFields = ['name', 'description', 'color'];
    const fields = Object.keys(updates).filter(f => allowedFields.includes(f));

    if (fields.length === 0) {
      throw new Error('No valid fields to update');
    }

    const values = fields.map(f => updates[f]);
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
      LEFT JOIN todos t ON p.id = t.project_id AND t.user_id = $1
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
    if (dueDate) {
      paramCount++;
      query += ` AND t.due_date <= $${paramCount}`;
      params.push(dueDate);
    }

    query += ' ORDER BY t.priority DESC, t.created_at ASC';

    const result = await this.query(query, params);
    return result.rows;
  }

  static async getTodosFiltered(user_id, options = {}) {
    const { projectId, category, status, startDate, endDate, limit } = options;

    let query = `
      SELECT t.*, p.name as project_name, p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.user_id = $1
    `;
    const params = [user_id];
    let paramCount = 1;

    // Filter by project/category (category maps to project name)
    if (projectId) {
      paramCount++;
      query += ` AND t.project_id = $${paramCount}`;
      params.push(projectId);
    } else if (category) {
      paramCount++;
      query += ` AND p.name = $${paramCount}`;
      params.push(category);
    }

    // Filter by status (handle 'overdue' as special case)
    if (status && status !== 'all') {
      if (status === 'overdue') {
        query += ` AND t.status = 'pending' AND t.due_date < CURRENT_DATE`;
      } else {
        paramCount++;
        query += ` AND t.status = $${paramCount}`;
        params.push(status);
      }
    }

    // Filter by date range
    if (startDate) {
      paramCount++;
      query += ` AND t.due_date >= $${paramCount}`;
      params.push(startDate);
    }
    if (endDate) {
      paramCount++;
      query += ` AND t.due_date <= $${paramCount}`;
      params.push(endDate);
    }

    query += ' ORDER BY t.priority DESC, t.created_at ASC';

    // Apply limit
    if (limit && Number.isInteger(limit) && limit > 0) {
      paramCount++;
      query += ` LIMIT $${paramCount}`;
      params.push(limit);
    }

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
      WHERE t.id = $1 AND t.user_id = $2
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
      WHERE t.user_id = $1
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
    const allowedFields = ['project_id', 'title', 'description', 'priority', 'status', 'estimated_hours', 'actual_hours', 'due_date', 'completed_date', 'tags', 'context'];
    const fields = Object.keys(updates).filter(f => allowedFields.includes(f));

    if (fields.length === 0) {
      throw new Error('No valid fields to update');
    }

    const values = fields.map(f => updates[f]);
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
    const result = await this.query(
      `
      DELETE FROM todos WHERE id = $1 AND user_id = $2 RETURNING *
    `,
      [id, user_id]
    );
    return result.rows[0];
  }

  static async searchTodos(user_id, query, category = null) {
    let sql = `
      SELECT t.*, p.name as project_name, p.color as project_color
      FROM todos t
      LEFT JOIN projects p ON t.project_id = p.id
      WHERE t.user_id = $1
        AND to_tsvector('english', t.title || ' ' || COALESCE(t.description, '')) @@ plainto_tsquery('english', $2)
    `;
    const params = [user_id, query];
    let paramCount = 2;

    if (category) {
      paramCount++;
      sql += ` AND p.name = $${paramCount}`;
      params.push(category);
    }

    sql += ' ORDER BY t.priority DESC, t.created_at ASC';

    const result = await this.query(sql, params);
    return result.rows;
  }

  // Analytics methods
  static async getCapacityStats(daysBack = 30) {
    // Validate and sanitize daysBack to prevent SQL injection
    const days = parseInt(daysBack, 10);
    if (isNaN(days) || days < 1 || days > 365) {
      throw new Error('Invalid daysBack parameter: must be between 1 and 365');
    }

    const result = await this.query(`
      SELECT
        DATE(completed_date) as date,
        SUM(actual_hours) as total_hours,
        COUNT(*) as tasks_completed
      FROM todos
      WHERE status = 'completed'
        AND completed_date >= NOW() - INTERVAL '1 day' * $1
      GROUP BY DATE(completed_date)
      ORDER BY date
    `, [days]);
    return result.rows;
  }

  static async getEstimationAccuracy(daysBack = 90) {
    // Validate and sanitize daysBack to prevent SQL injection
    const days = parseInt(daysBack, 10);
    if (isNaN(days) || days < 1 || days > 365) {
      throw new Error('Invalid daysBack parameter: must be between 1 and 365');
    }

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
        AND completed_date >= NOW() - INTERVAL '1 day' * $1
        AND estimated_hours > 0
      ORDER BY completed_date DESC
    `, [days]);
    return result.rows;
  }

  // API Key methods
  static async createApiKey(userId, apiKey) {
    // Use bcrypt with 12 rounds (secure and performant)
    const hashedKey = await bcrypt.hash(apiKey, 12);
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
  static async createOAuthClient(
    clientId,
    clientSecret,
    name,
    redirectUris,
    grantTypes = ['authorization_code'],
    scopes = ['read'],
    userId = null
  ) {
    // Use bcrypt with 12 rounds for secure password hashing
    const hashedSecret = await bcrypt.hash(clientSecret, 12);
    const result = await this.query(
      `
      INSERT INTO oauth_clients (client_id, client_secret_hash, name, redirect_uris, grant_types, scopes, user_id, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
      RETURNING id, client_id, name, redirect_uris, user_id
    `,
      [
        clientId,
        hashedSecret,
        name,
        JSON.stringify(redirectUris),
        JSON.stringify(grantTypes),
        JSON.stringify(scopes),
        userId,
      ]
    );
    return result.rows[0];
  }

  static async getOAuthClient(clientId) {
    const result = await this.query(
      `
      SELECT id, client_id, name, redirect_uris, grant_types, scopes, is_active
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
      SELECT id, client_id, name, redirect_uris, grant_types, scopes, client_secret_hash, user_id
      FROM oauth_clients
      WHERE client_id = $1 AND is_active = true
    `,
      [clientId]
    );

    if (result.rows.length === 0) {
      return null;
    }

    const client = result.rows[0];

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
        FOR UPDATE
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
        FOR UPDATE
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
