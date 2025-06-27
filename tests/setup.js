import { config } from 'dotenv';

// Load test environment variables
config({ path: '.env.test' });

// Set test environment
process.env.NODE_ENV = 'test';

// Use a test database
if (!process.env.POSTGRES_DB?.includes('test')) {
  process.env.POSTGRES_DB = process.env.POSTGRES_DB
    ? `${process.env.POSTGRES_DB}_test`
    : 'taskmanager_test';
}

console.log('Test setup complete. Using database:', process.env.POSTGRES_DB);
