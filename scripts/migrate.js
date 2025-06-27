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
  ALTER TABLE sessions ALTER COLUMN id TYPE VARCHAR (255);
  
`;

  const downTemplate = `-- Rollback for: ${name}
-- Created: ${new Date().toISOString()}
  ALTER TABLE sessions ALTER COLUMN id TYPE SERIAL;
  
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
