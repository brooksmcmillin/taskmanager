import pg from 'pg';
const { Pool } = pg;
import { config } from 'dotenv';
import crypto from 'crypto';

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
    const fields = Object.keys(updates);
    const values = Object.values(updates);
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

  // API Key methods
  static async createApiKey(userId, apiKey) {
    const hashedKey = crypto.createHash('sha256').update(apiKey).digest('hex');
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
    const hashedKey = crypto.createHash('sha256').update(apiKey).digest('hex');
    const result = await this.query(
      `
      SELECT u.*, ak.id as api_key_id 
      FROM users u 
      JOIN api_keys ak ON u.id = ak.user_id 
      WHERE ak.key_hash = $1 AND ak.is_active = true AND u.is_active = true
    `,
      [hashedKey]
    );

    return result.rows[0];
  }

  static async revokeApiKey(userId, apiKey) {
    const hashedKey = crypto.createHash('sha256').update(apiKey).digest('hex');
    const result = await this.query(
      `
      UPDATE api_keys 
      SET is_active = false
      WHERE user_id = $1 AND key_hash = $2
      RETURNING id
    `,
      [userId, hashedKey]
    );
    return result.rows[0];
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
    scopes = ['read']
  ) {
    const hashedSecret = crypto
      .createHash('sha256')
      .update(clientSecret)
      .digest('hex');
    const result = await this.query(
      `
      INSERT INTO oauth_clients (client_id, client_secret_hash, name, redirect_uris, grant_types, scopes, created_at)
      VALUES ($1, $2, $3, $4, $5, $6, NOW())
      RETURNING id, client_id, name, redirect_uris
    `,
      [
        clientId,
        hashedSecret,
        name,
        JSON.stringify(redirectUris),
        JSON.stringify(grantTypes),
        JSON.stringify(scopes),
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
    const hashedSecret = crypto
      .createHash('sha256')
      .update(clientSecret)
      .digest('hex');
    const result = await this.query(
      `
      SELECT id, client_id, name, redirect_uris, grant_types, scopes
      FROM oauth_clients 
      WHERE client_id = $1 AND client_secret_hash = $2 AND is_active = true
    `,
      [clientId, hashedSecret]
    );
    return result.rows[0];
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
}
