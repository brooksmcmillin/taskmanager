import { MigrationRunner } from '../src/lib/migrations.js';
import { config } from 'dotenv';
import path from 'path';
import fs from 'fs';
import pg from 'pg';

config();

const database_url =
  'postgresql://' +
  process.env.POSTGRES_USER +
  ':' +
  process.env.POSTGRES_PASSWORD +
  '@localhost:5432/' +
  process.env.POSTGRES_DB;
const runner = new MigrationRunner(database_url);

const command = process.argv[2];
const migrationName = process.argv[3];

switch (command) {
  case 'up':
    await runner.runMigrations();
    break;
  case 'create':
    if (!migrationName) {
      console.error('Usage: npm run migrate create <migration_name>');
      process.exit(1);
    }
    await createMigration(migrationName);
    break;
  case 'rollback':
    if (!migrationName) {
      console.error('Usage: npm run migrate rollback <migration_version>');
      process.exit(1);
    }
    await rollbackMigration(migrationName);
    break;
  default:
    console.log(`
Migration Commands:
  npm run migrate up              - Run all pending migrations
  npm run migrate create <name>   - Create a new migration
  npm run migrate rollback <ver>  - Rollback a specific migration
    `);
}

await runner.close();

function errorHandler(err) {
  if (err) {
    return console.log(err);
  }
}

async function createMigration(name) {
  const timestamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '');
  const version = `${timestamp}_${name}`;

  const migrationsDir = path.join(process.cwd(), 'src/migrations');
  // wait fs.mkdir(migrationsDir, { recursive: true });

  const upTemplate = `-- Migration: ${name}
-- Created: ${new Date().toISOString()}
-- Initialize OAuth database schema
-- This assumes the main TaskManager database schema already exists

-- Create OAuth clients table
CREATE TABLE IF NOT EXISTS oauth_clients (
  id SERIAL PRIMARY KEY,
  client_id VARCHAR(255) UNIQUE NOT NULL,
  client_secret_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  redirect_uris TEXT NOT NULL,
  grant_types TEXT NOT NULL DEFAULT '["authorization_code"]',
  scopes TEXT NOT NULL DEFAULT '["read"]',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create authorization codes table
CREATE TABLE IF NOT EXISTS authorization_codes (
  id SERIAL PRIMARY KEY,
  code VARCHAR(255) UNIQUE NOT NULL,
  client_id VARCHAR(255) NOT NULL REFERENCES oauth_clients(client_id),
  user_id INTEGER NOT NULL REFERENCES users(id),
  redirect_uri VARCHAR(500) NOT NULL,
  scopes TEXT NOT NULL,
  code_challenge VARCHAR(255),
  code_challenge_method VARCHAR(10),
  expires_at TIMESTAMP NOT NULL,
  used BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create access tokens table
CREATE TABLE IF NOT EXISTS access_tokens (
  id SERIAL PRIMARY KEY,
  token VARCHAR(255) UNIQUE NOT NULL,
  refresh_token VARCHAR(255) UNIQUE NOT NULL,
  user_id INTEGER NOT NULL REFERENCES users(id),
  client_id VARCHAR(255) NOT NULL REFERENCES oauth_clients(client_id),
  scopes TEXT NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_oauth_clients_client_id ON oauth_clients(client_id);
CREATE INDEX IF NOT EXISTS idx_authorization_codes_code ON authorization_codes(code);
CREATE INDEX IF NOT EXISTS idx_access_tokens_token ON access_tokens(token);
CREATE INDEX IF NOT EXISTS idx_access_tokens_refresh_token ON access_tokens(refresh_token);

`;

  const downTemplate = `-- Rollback for: ${name}
-- Created: ${new Date().toISOString()}
-- Remove OAuth database schema

-- Drop indexes first
DROP INDEX IF EXISTS idx_oauth_clients_client_id;
DROP INDEX IF EXISTS idx_authorization_codes_code;
DROP INDEX IF EXISTS idx_access_tokens_token;
DROP INDEX IF EXISTS idx_access_tokens_refresh_token;

-- Drop tables in reverse order due to foreign key constraints
DROP TABLE IF EXISTS access_tokens;
DROP TABLE IF EXISTS authorization_codes;
DROP TABLE IF EXISTS oauth_clients;
`;

  await fs.writeFile(
    path.join(migrationsDir, `${version}.up.sql`),
    upTemplate,
    errorHandler
  );

  await fs.writeFile(
    path.join(migrationsDir, `${version}.down.sql`),
    downTemplate,
    errorHandler
  );

  console.log(`✅ Created migration files:
  - src/migrations/${version}.up.sql
  - src/migrations/${version}.down.sql`);
}

async function rollbackMigration(version) {
  const migrationsDir = path.join(process.cwd(), 'src/migrations');
  const downFile = path.join(migrationsDir, `${version}.down.sql`);

  try {
    const downSql = await fs.readFile(downFile, 'utf8');
    await runner.rollbackMigration(version, downSql);
  } catch (error) {
    console.error(`❌ Could not rollback migration ${version}:`, error.message);
  }
}
