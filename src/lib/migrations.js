import pg from 'pg';
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const { Pool } = pg;
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export class MigrationRunner {
  constructor(connectionString) {
    this.pool = new Pool({ connectionString });
  }

  async ensureMigrationsTable() {
    await this.pool.query(`
      CREATE TABLE IF NOT EXISTS schema_migrations (
        version VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMP DEFAULT NOW(),
        checksum VARCHAR(64)
      );
    `);
  }

  async getAppliedMigrations() {
    const result = await this.pool.query(
      'SELECT version FROM schema_migrations ORDER BY version'
    );
    return result.rows.map((row) => row.version);
  }

  async applyMigration(version, sql, checksum) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      // Apply the migration
      await client.query(sql);

      // Record that it was applied
      await client.query(
        'INSERT INTO schema_migrations (version, checksum) VALUES ($1, $2)',
        [version, checksum]
      );

      await client.query('COMMIT');
      console.log(`✅ Applied migration ${version}`);
    } catch (error) {
      await client.query('ROLLBACK');
      throw new Error(`❌ Migration ${version} failed: ${error.message}`);
    } finally {
      client.release();
    }
  }

  async rollbackMigration(version, downSql) {
    const client = await this.pool.connect();
    try {
      await client.query('BEGIN');

      // Apply the down migration
      await client.query(downSql);

      // Remove from migrations table
      await client.query('DELETE FROM schema_migrations WHERE version = $1', [
        version,
      ]);

      await client.query('COMMIT');
      console.log(`↩️ Rolled back migration ${version}`);
    } catch (error) {
      await client.query('ROLLBACK');
      throw new Error(`❌ Rollback ${version} failed: ${error.message}`);
    } finally {
      client.release();
    }
  }

  async runMigrations() {
    await this.ensureMigrationsTable();

    const migrationsDir = path.join(__dirname, '../migrations');
    const appliedMigrations = await this.getAppliedMigrations();

    let migrationFiles;
    try {
      migrationFiles = await fs.readdir(migrationsDir);
    } catch (error) {
      console.log('No migrations directory found, creating...');
      await fs.mkdir(migrationsDir, { recursive: true });
      migrationFiles = [];
    }

    const sqlFiles = migrationFiles
      .filter((file) => file.endsWith('.up.sql'))
      .sort();

    for (const file of sqlFiles) {
      const version = file.replace('.up.sql', '');

      if (appliedMigrations.includes(version)) {
        console.log(`⏭️ Skipping already applied migration ${version}`);
        continue;
      }

      const migrationPath = path.join(migrationsDir, file);
      const sql = await fs.readFile(migrationPath, 'utf8');
      const checksum = this.generateChecksum(sql);

      await this.applyMigration(version, sql, checksum);
    }

    console.log('✅ All migrations completed');
  }

  generateChecksum(content) {
    // Simple checksum - in production, use crypto.createHash
    return Buffer.from(content).toString('base64').slice(0, 8);
  }

  async close() {
    await this.pool.end();
  }
}
