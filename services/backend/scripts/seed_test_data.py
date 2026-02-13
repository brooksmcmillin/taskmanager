"""Seed test data for TaskManager.

This script creates a test user, projects, and tasks for testing the filtering
feature. It validates that it's running against a development/test database
before making changes.

Usage:
    uv run python scripts/seed_test_data.py [--user-email EMAIL] [--skip-confirm]
"""

import argparse
import asyncio
import random
import sys
from datetime import date, timedelta
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import hash_password
from app.db.database import async_session_maker
from app.models.project import Project
from app.models.todo import Priority, Status, Todo
from app.models.user import User

# Test data configuration
DEFAULT_TEST_EMAIL = "test@example.com"
DEFAULT_TEST_PASSWORD = "TestPass123!"  # pragma: allowlist secret

# Project names and colors
PROJECTS = [
    {"name": "Work", "color": "#3b82f6", "description": "Work-related tasks"},
    {
        "name": "Personal",
        "color": "#10b981",
        "description": "Personal tasks and errands",
    },
    {
        "name": "Learning",
        "color": "#f59e0b",
        "description": "Learning and skill development",
    },
    {"name": "Health", "color": "#ef4444", "description": "Health and fitness goals"},
    {"name": "Home", "color": "#8b5cf6", "description": "Home improvement and chores"},
]

# Task templates for variety
TASK_TEMPLATES = [
    "Review {topic} documentation",
    "Complete {topic} assignment",
    "Schedule {topic} meeting",
    "Research {topic} options",
    "Update {topic} status report",
    "Fix {topic} bug",
    "Implement {topic} feature",
    "Test {topic} functionality",
    "Deploy {topic} changes",
    "Write {topic} proposal",
    "Organize {topic} files",
    "Clean {topic} area",
    "Practice {topic} skills",
    "Plan {topic} strategy",
    "Review {topic} feedback",
]

TOPICS = [
    "API",
    "database",
    "frontend",
    "backend",
    "security",
    "performance",
    "documentation",
    "testing",
    "deployment",
    "monitoring",
    "analytics",
    "kitchen",
    "bedroom",
    "garage",
    "garden",
    "office",
    "gym",
    "budget",
    "schedule",
    "diet",
    "exercise",
    "meditation",
    "reading",
]


def validate_database_safe() -> bool:
    """Validate that we're not running against a production database.

    Returns:
        bool: True if safe to proceed, False otherwise
    """
    db_name = settings.postgres_db.lower()

    # Reject if database name contains production indicators
    dangerous_names = ["prod", "production", "live", "main"]
    if any(name in db_name for name in dangerous_names):
        print(
            f"❌ ERROR: Database '{settings.postgres_db}' appears to be a "
            "production database!"
        )
        print("   This script should only run against development or test databases.")
        return False

    # Warn if not clearly a dev/test database
    safe_names = ["dev", "test", "development", "local", "taskmanager"]
    if not any(name in db_name for name in safe_names):
        print(
            f"⚠️  WARNING: Database name '{settings.postgres_db}' doesn't "
            "clearly indicate dev/test."
        )
        return False

    return True


async def cleanup_test_data(session: AsyncSession, user_email: str) -> None:
    """Clean up existing test data for the specified user.

    Args:
        session: Database session
        user_email: Email of the test user to clean up
    """
    print(f"\n🧹 Cleaning up existing test data for {user_email}...")

    # Find the test user
    result = await session.execute(select(User).where(User.email == user_email))
    user = result.scalar_one_or_none()

    if not user:
        print(f"   No existing user found with email {user_email}")
        return

    # Count existing data
    todos_result = await session.execute(select(Todo).where(Todo.user_id == user.id))
    todos_count = len(todos_result.scalars().all())

    projects_result = await session.execute(
        select(Project).where(Project.user_id == user.id)
    )
    projects_count = len(projects_result.scalars().all())

    print(f"   Found {todos_count} tasks and {projects_count} projects")

    # Delete all todos and projects (cascades will handle related data)
    await session.execute(delete(Todo).where(Todo.user_id == user.id))
    await session.execute(delete(Project).where(Project.user_id == user.id))

    # Delete the user (cascades will handle sessions, etc.)
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()

    print(f"   ✅ Cleaned up user, {todos_count} tasks, and {projects_count} projects")


async def create_test_user(session: AsyncSession, email: str) -> User:
    """Create a test user.

    Args:
        session: Database session
        email: Email address for the user

    Returns:
        User: Created user instance
    """
    print(f"\n👤 Creating test user: {email}")

    user = User(
        email=email,
        password_hash=hash_password(DEFAULT_TEST_PASSWORD),
        is_active=True,
        is_admin=False,
    )

    session.add(user)
    await session.flush()  # Get the user ID

    print(f"   ✅ Created user (ID: {user.id})")
    print(f"   📧 Email: {email}")
    print(f"   📧 Email: {email}")
    print(f"   🔐 Password: {DEFAULT_TEST_PASSWORD}")

    return user


async def create_projects(session: AsyncSession, user: User) -> list[Project]:
    """Create test projects.

    Args:
        session: Database session
        user: User who owns the projects

    Returns:
        list[Project]: Created projects
    """
    print(f"\n📁 Creating {len(PROJECTS)} projects...")

    projects = []
    for project_data in PROJECTS:
        project = Project(
            user_id=user.id,
            name=project_data["name"],
            description=project_data["description"],
            color=project_data["color"],
            is_active=True,
        )
        session.add(project)
        projects.append(project)

    await session.flush()  # Get project IDs

    for project in projects:
        print(f"   ✅ {project.name} (ID: {project.id}, Color: {project.color})")

    return projects


def generate_task_title() -> str:
    """Generate a random task title."""
    template = random.choice(TASK_TEMPLATES)
    topic = random.choice(TOPICS)
    return template.format(topic=topic)


def generate_due_date() -> date | None:
    """Generate a due date or None (10% chance of None).

    Returns:
        date | None: Due date 0-14 days from today, or None
    """
    # 10% chance of no due date
    if random.random() < 0.1:
        return None

    # Random date 0-14 days from today
    days_ahead = random.randint(0, 14)
    return date.today() + timedelta(days=days_ahead)


async def create_tasks(
    session: AsyncSession,
    user: User,
    projects: list[Project],
    tasks_per_project: int = 10,
) -> list[Todo]:
    """Create test tasks for each project.

    Args:
        session: Database session
        user: User who owns the tasks
        projects: Projects to create tasks under
        tasks_per_project: Number of tasks to create per project

    Returns:
        list[Todo]: Created tasks
    """
    print(f"\n📝 Creating {tasks_per_project} tasks per project...")

    todos = []
    priorities = list(Priority)

    total_tasks = len(projects) * tasks_per_project
    tasks_without_due_date = 0

    for project in projects:
        project_tasks = []

        for _i in range(tasks_per_project):
            due_date = generate_due_date()
            if due_date is None:
                tasks_without_due_date += 1

            # Random priority weighted toward medium
            priority = random.choices(
                priorities,
                weights=[20, 50, 25, 5],  # low, medium, high, urgent
            )[0]

            # Random estimated hours (1-8 hours)
            estimated_hours = (
                random.choice([1, 2, 3, 4, 5, 6, 8]) if random.random() > 0.3 else None
            )

            # Some tasks have tags
            tags = []
            if random.random() > 0.5:
                tag_options = [
                    "urgent",
                    "blocked",
                    "review",
                    "documentation",
                    "bug",
                    "feature",
                ]
                tags = random.sample(tag_options, k=random.randint(1, 2))

            todo = Todo(
                user_id=user.id,
                project_id=project.id,
                title=generate_task_title(),
                description=f"This is a test task for the {project.name} project.",
                priority=priority,
                status=Status.pending,
                due_date=due_date,
                estimated_hours=estimated_hours,
                tags=tags,
            )

            session.add(todo)
            project_tasks.append(todo)

        todos.extend(project_tasks)
        print(f"   ✅ {project.name}: {len(project_tasks)} tasks")

    await session.flush()

    print("\n📊 Summary:")
    print(f"   Total tasks: {total_tasks}")
    print(f"   Tasks with due dates: {total_tasks - tasks_without_due_date}")
    pct = tasks_without_due_date / total_tasks * 100
    print(f"   Tasks without due dates: {tasks_without_due_date} ({pct:.1f}%)")

    return todos


async def seed_data(user_email: str, skip_confirm: bool = False) -> None:
    """Seed the database with test data.

    Args:
        user_email: Email for the test user
        skip_confirm: Skip confirmation prompt
    """
    print("=" * 70)
    print("TaskManager Test Data Seeder")
    print("=" * 70)

    # Validate database is safe
    if not validate_database_safe():
        sys.exit(1)

    print(f"\n📊 Database: {settings.postgres_db}")
    print(f"   Host: {settings.postgres_host}:{settings.postgres_port}")
    print(f"   User: {settings.postgres_user}")

    # Confirm before proceeding
    if not skip_confirm:
        print(
            "\n⚠️  This will DELETE all existing data for the test user "
            "and create new data."
        )
        response = input("   Continue? [y/N]: ")
        if response.lower() != "y":
            print("❌ Aborted")
            sys.exit(0)

    # Create database session
    async with async_session_maker() as session:
        try:
            # Clean up existing test data
            await cleanup_test_data(session, user_email)

            # Create test user
            user = await create_test_user(session, user_email)

            # Create projects
            projects = await create_projects(session, user)

            # Create tasks
            await create_tasks(session, user, projects, tasks_per_project=10)

            # Commit all changes
            await session.commit()

            print("\n" + "=" * 70)
            print("✅ Test data seeded successfully!")
            print("=" * 70)
            print("\n🔑 Login credentials:")
            print(f"   Email: {user.email}")
            print(f"   Password: {DEFAULT_TEST_PASSWORD}")
            print("💡 Tip: Use the project filter dropdown to filter tasks by project!")

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error seeding data: {e}")
            raise


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Seed test data for TaskManager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--user-email",
        default=DEFAULT_TEST_EMAIL,
        help=f"Email for test user (default: {DEFAULT_TEST_EMAIL})",
    )
    parser.add_argument(
        "--skip-confirm",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--tasks-per-project",
        type=int,
        default=10,
        help="Number of tasks to create per project (default: 10)",
    )

    args = parser.parse_args()

    # Run the async seeding function
    asyncio.run(seed_data(args.user_email, args.skip_confirm))


if __name__ == "__main__":
    main()
