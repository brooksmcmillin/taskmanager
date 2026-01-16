"""Tests for recurring tasks endpoints."""

from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.recurring_task import RecurringTask
from app.models.user import User


@pytest.mark.asyncio
async def test_list_recurring_tasks_unauthenticated(client: AsyncClient):
    """Test listing recurring tasks without authentication."""
    response = await client.get("/api/recurring-tasks")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_002"


@pytest.mark.asyncio
async def test_list_recurring_tasks_empty(authenticated_client: AsyncClient):
    """Test listing recurring tasks when none exist."""
    response = await authenticated_client.get("/api/recurring-tasks")

    assert response.status_code == 200
    data = response.json()
    assert data["recurring_tasks"] == []


@pytest.mark.asyncio
async def test_create_recurring_task_daily(authenticated_client: AsyncClient):
    """Test creating a daily recurring task."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Daily Standup",
            "frequency": "daily",
            "start_date": "2026-01-15",
            "interval_value": 1,
            "priority": "high",
            "description": "Morning standup meeting",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Daily Standup"
    assert data["frequency"] == "daily"
    assert data["interval_value"] == 1
    assert data["priority"] == "high"
    assert data["is_active"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_recurring_task_weekly_with_weekdays(
    authenticated_client: AsyncClient,
):
    """Test creating a weekly recurring task with specific weekdays."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Weekly Review",
            "frequency": "weekly",
            "start_date": "2026-01-15",
            "interval_value": 1,
            "weekdays": [1, 3, 5],  # Monday, Wednesday, Friday
            "priority": "medium",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["frequency"] == "weekly"
    assert data["weekdays"] == [1, 3, 5]


@pytest.mark.asyncio
async def test_create_recurring_task_monthly_with_day(
    authenticated_client: AsyncClient,
):
    """Test creating a monthly recurring task with day of month."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Monthly Report",
            "frequency": "monthly",
            "start_date": "2026-01-15",
            "interval_value": 1,
            "day_of_month": 15,
            "priority": "urgent",
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["frequency"] == "monthly"
    assert data["day_of_month"] == 15


@pytest.mark.asyncio
async def test_create_recurring_task_invalid_weekdays(
    authenticated_client: AsyncClient,
):
    """Test creating a recurring task with invalid weekdays."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Invalid Weekdays",
            "frequency": "weekly",
            "start_date": "2026-01-15",
            "weekdays": [7, 8],  # Invalid: must be 0-6
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_recurring_task_invalid_day_of_month(
    authenticated_client: AsyncClient,
):
    """Test creating a recurring task with invalid day of month."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Invalid Day",
            "frequency": "monthly",
            "start_date": "2026-01-15",
            "day_of_month": 32,  # Invalid: must be 1-31
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_recurring_task_invalid_priority(
    authenticated_client: AsyncClient,
):
    """Test creating a recurring task with invalid priority."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Invalid Priority",
            "frequency": "daily",
            "start_date": "2026-01-15",
            "priority": "super_critical",  # Invalid priority
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_create_recurring_task_with_nonexistent_project(
    authenticated_client: AsyncClient,
):
    """Test creating a recurring task with a project that doesn't exist."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Task with Bad Project",
            "frequency": "daily",
            "start_date": "2026-01-15",
            "project_id": 99999,
        },
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_004"


@pytest.mark.asyncio
async def test_create_recurring_task_with_valid_project(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test creating a recurring task with a valid project."""
    # Create a project first
    project = Project(
        user_id=test_user.id,
        name="Work",
        color="#3b82f6",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)

    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Task with Project",
            "frequency": "daily",
            "start_date": "2026-01-15",
            "project_id": project.id,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["project_id"] == project.id


@pytest.mark.asyncio
async def test_get_recurring_task(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test getting a specific recurring task."""
    # Create a recurring task
    task = RecurringTask(
        user_id=test_user.id,
        title="Get This Task",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    response = await authenticated_client.get(f"/api/recurring-tasks/{task.id}")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["id"] == task.id
    assert data["title"] == "Get This Task"


@pytest.mark.asyncio
async def test_get_recurring_task_not_found(authenticated_client: AsyncClient):
    """Test getting a recurring task that doesn't exist."""
    response = await authenticated_client.get("/api/recurring-tasks/99999")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_006"


@pytest.mark.asyncio
async def test_update_recurring_task(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test updating a recurring task."""
    # Create a recurring task
    task = RecurringTask(
        user_id=test_user.id,
        title="Update Me",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
        priority="low",
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Update it
    response = await authenticated_client.put(
        f"/api/recurring-tasks/{task.id}",
        json={
            "title": "Updated Title",
            "priority": "urgent",
            "interval_value": 2,
        },
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["title"] == "Updated Title"
    assert data["priority"] == "urgent"
    assert data["interval_value"] == 2


@pytest.mark.asyncio
async def test_update_recurring_task_with_no_fields(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test updating a recurring task with no fields (should fail)."""
    # Create a recurring task
    task = RecurringTask(
        user_id=test_user.id,
        title="Update Me",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Try to update with empty body
    response = await authenticated_client.put(
        f"/api/recurring-tasks/{task.id}",
        json={},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "VALIDATION_009"


@pytest.mark.asyncio
async def test_delete_recurring_task(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test deleting (deactivating) a recurring task."""
    # Create a recurring task
    task = RecurringTask(
        user_id=test_user.id,
        title="Delete Me",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
        is_active=True,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Delete (soft delete) it
    response = await authenticated_client.delete(f"/api/recurring-tasks/{task.id}")

    assert response.status_code == 200
    assert response.json()["data"]["deleted"] is True

    # Verify it's deactivated by checking it's not in active list
    list_response = await authenticated_client.get(
        "/api/recurring-tasks?active_only=true"
    )
    assert all(t["id"] != task.id for t in list_response.json()["recurring_tasks"])

    # Verify it's still accessible when active_only=false
    list_response = await authenticated_client.get(
        "/api/recurring-tasks?active_only=false"
    )
    inactive_tasks = [
        t for t in list_response.json()["recurring_tasks"] if t["id"] == task.id
    ]
    assert len(inactive_tasks) == 1
    assert inactive_tasks[0]["is_active"] is False


@pytest.mark.asyncio
async def test_list_recurring_tasks_active_only(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test listing recurring tasks with active_only filter."""
    # Create active and inactive tasks
    active_task = RecurringTask(
        user_id=test_user.id,
        title="Active Task",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
        is_active=True,
    )
    inactive_task = RecurringTask(
        user_id=test_user.id,
        title="Inactive Task",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
        is_active=False,
    )
    db_session.add_all([active_task, inactive_task])
    await db_session.commit()

    # List active only (default)
    response = await authenticated_client.get("/api/recurring-tasks")
    assert response.status_code == 200
    tasks = response.json()["recurring_tasks"]
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Active Task"

    # List all including inactive
    response = await authenticated_client.get("/api/recurring-tasks?active_only=false")
    assert response.status_code == 200
    tasks = response.json()["recurring_tasks"]
    assert len(tasks) == 2


@pytest.mark.asyncio
async def test_update_recurring_task_with_invalid_project(
    authenticated_client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
):
    """Test updating a recurring task with an invalid project."""
    # Create a recurring task
    task = RecurringTask(
        user_id=test_user.id,
        title="Update Me",
        frequency="daily",
        start_date=date(2026, 1, 15),
        next_due_date=date(2026, 1, 15),
        interval_value=1,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)

    # Try to update with invalid project
    response = await authenticated_client.put(
        f"/api/recurring-tasks/{task.id}",
        json={"project_id": 99999},
    )

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "NOT_FOUND_004"


@pytest.mark.asyncio
async def test_recurring_task_with_all_fields(authenticated_client: AsyncClient):
    """Test creating a recurring task with all optional fields."""
    response = await authenticated_client.post(
        "/api/recurring-tasks",
        json={
            "title": "Complete Task",
            "frequency": "weekly",
            "start_date": "2026-01-15",
            "end_date": "2026-12-31",
            "interval_value": 2,
            "weekdays": [0, 6],  # Sunday and Saturday
            "description": "Weekend task",
            "priority": "high",
            "estimated_hours": 2.5,
            "tags": ["weekend", "personal"],
            "context": "home",
            "skip_missed": False,
        },
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Complete Task"
    assert data["end_date"] == "2026-12-31"
    assert data["estimated_hours"] == 2.5
    assert data["tags"] == ["weekend", "personal"]
    assert data["context"] == "home"
    assert data["skip_missed"] is False
