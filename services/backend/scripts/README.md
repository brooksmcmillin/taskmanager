# Backend Scripts

Utility scripts for TaskManager backend development and testing.

## Test Data Seeder

The `seed_test_data.py` script creates realistic test data for development and testing.

### Features

- ✅ **Database Safety Checks**: Validates that you're not running against a production database
- 🧹 **Auto Cleanup**: Removes existing test data before seeding new data
- 👤 **Test User Creation**: Creates a test user with known credentials
- 📁 **Multiple Projects**: Creates 5 projects with different colors and themes
- 📝 **Realistic Tasks**: Generates tasks with:
  - Random priorities (weighted toward medium)
  - Due dates distributed over 0-14 days (90% of tasks)
  - No due date for 10% of tasks
  - Random estimated hours
  - Variety of titles and tags

### Usage

**Basic usage** (creates test@example.com user):
```bash
cd services/backend
uv run python scripts/seed_test_data.py
```

**Custom email**:
```bash
uv run python scripts/seed_test_data.py --user-email mytest@example.com
```

**Skip confirmation** (for automation):
```bash
uv run python scripts/seed_test_data.py --skip-confirm
```

**Custom number of tasks**:
```bash
uv run python scripts/seed_test_data.py --tasks-per-project 20
```

### Login Credentials

After running the script, you can log in with:
- **Username**: `testuser` (login uses username, not email!)
- **Password**: `TestPass123!`
- Email: `test@example.com` (or your custom email - used for display only)

### Database Safety

The script includes multiple safety checks:

1. **Rejects production databases**: Won't run if database name contains "prod", "production", "live", or "main"
2. **Warns for unclear databases**: Prompts confirmation if database name doesn't indicate dev/test
3. **Requires confirmation**: Asks for confirmation before making changes (unless `--skip-confirm`)

### What Gets Created

- **1 Test User**: With known login credentials
- **5 Projects**:
  - Work (blue)
  - Personal (green)
  - Learning (orange)
  - Health (red)
  - Home (purple)
- **50 Tasks** (default, 10 per project):
  - Varied priorities
  - Mix of due dates and no due dates
  - Random estimated hours
  - Some with tags

### Example Output

```
======================================================================
TaskManager Test Data Seeder
======================================================================

📊 Database: taskmanager
   Host: localhost:5432
   User: taskmanager

⚠️  This will DELETE all existing data for the test user and create new data.
   Continue? [y/N]: y

🧹 Cleaning up existing test data for test@example.com...
   Found 50 tasks and 5 projects
   ✅ Cleaned up user, 50 tasks, and 5 projects

👤 Creating test user: test@example.com
   ✅ Created user (ID: 1)
   👤 Username: testuser
   📧 Email: test@example.com
   🔐 Password: TestPass123!

📁 Creating 5 projects...
   ✅ Work (ID: 1, Color: #3b82f6)
   ✅ Personal (ID: 2, Color: #10b981)
   ✅ Learning (ID: 3, Color: #f59e0b)
   ✅ Health (ID: 4, Color: #ef4444)
   ✅ Home (ID: 5, Color: #8b5cf6)

📝 Creating 10 tasks per project...
   ✅ Work: 10 tasks
   ✅ Personal: 10 tasks
   ✅ Learning: 10 tasks
   ✅ Health: 10 tasks
   ✅ Home: 10 tasks

📊 Summary:
   Total tasks: 50
   Tasks with due dates: 46
   Tasks without due dates: 4 (8.0%)

======================================================================
✅ Test data seeded successfully!
======================================================================

🔑 Login credentials:
   Username: testuser
   Password: TestPass123!
   (Email: test@example.com)

⚠️  IMPORTANT: Login with USERNAME, not email!
💡 Tip: Use the project filter dropdown to filter tasks by project!
```

### Troubleshooting

**Database connection errors**:
- Make sure PostgreSQL is running: `docker compose up -d postgres`
- Check your `.env` file has correct database credentials

**Import errors**:
- Run from the backend directory: `cd services/backend`
- Use `uv run` to execute in the virtual environment

**Permission errors**:
- The script needs permission to delete and create data
- Make sure you're running against your local development database
