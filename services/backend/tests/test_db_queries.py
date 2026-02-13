"""Tests for database query helpers in app/db/queries.py."""

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.errors import errors
from app.db.queries import (
    get_next_position,
    get_resource_for_user,
    get_resources_for_user,
    verify_resource_exists,
)
from app.models.project import Project
from app.models.todo import Priority, Status, Todo
from app.models.user import User


@pytest.fixture
async def test_user(db_session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        password_hash="hashed",  # pragma: allowlist secret
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def other_user(db_session):
    """Create another test user for authorization tests."""
    user = User(
        email="other@example.com",
        password_hash="hashed",  # pragma: allowlist secret
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_todo(db_session, test_user):
    """Create a test todo."""
    todo = Todo(
        user_id=test_user.id,
        title="Test Todo",
        priority=Priority.medium,
        status=Status.pending,
        position=1,
    )
    db_session.add(todo)
    await db_session.flush()
    return todo


@pytest.fixture
async def deleted_todo(db_session, test_user):
    """Create a soft-deleted todo."""
    todo = Todo(
        user_id=test_user.id,
        title="Deleted Todo",
        priority=Priority.medium,
        status=Status.pending,
        position=2,
        deleted_at=datetime.now(UTC),
    )
    db_session.add(todo)
    await db_session.flush()
    return todo


@pytest.fixture
async def test_project(db_session, test_user):
    """Create a test project."""
    project = Project(
        user_id=test_user.id,
        name="Test Project",
        position=1,
    )
    db_session.add(project)
    await db_session.flush()
    return project


class TestGetResourceForUser:
    """Tests for get_resource_for_user function."""

    async def test_returns_resource_for_valid_user(
        self, db_session, test_user, test_todo
    ):
        """Should return the resource when user owns it."""
        result = await get_resource_for_user(
            db_session, Todo, test_todo.id, test_user.id, errors.todo_not_found
        )
        assert result.id == test_todo.id
        assert result.title == "Test Todo"

    async def test_raises_error_for_wrong_user(self, db_session, test_todo, other_user):
        """Should raise error when resource belongs to different user."""
        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session, Todo, test_todo.id, other_user.id, errors.todo_not_found
            )
        assert exc_info.value.status_code == 404

    async def test_raises_error_for_nonexistent_resource(self, db_session, test_user):
        """Should raise error when resource doesn't exist."""
        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session, Todo, 99999, test_user.id, errors.todo_not_found
            )
        assert exc_info.value.status_code == 404

    async def test_excludes_deleted_resources_by_default(
        self, db_session, test_user, deleted_todo
    ):
        """Should not find soft-deleted resources by default."""
        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session, Todo, deleted_todo.id, test_user.id, errors.todo_not_found
            )
        assert exc_info.value.status_code == 404

    async def test_includes_deleted_when_check_deleted_false(
        self, db_session, test_user, deleted_todo
    ):
        """Should find soft-deleted resources when check_deleted=False."""
        result = await get_resource_for_user(
            db_session,
            Todo,
            deleted_todo.id,
            test_user.id,
            errors.todo_not_found,
            check_deleted=False,
        )
        assert result.id == deleted_todo.id

    async def test_works_with_models_without_deleted_at(
        self, db_session, test_user, test_project
    ):
        """Should work correctly for models without deleted_at column."""
        result = await get_resource_for_user(
            db_session,
            Project,
            test_project.id,
            test_user.id,
            errors.project_not_found,
        )
        assert result.id == test_project.id

    async def test_uses_custom_error_factory(self, db_session, test_user):
        """Should use the provided error factory for the exception."""
        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session,
                Project,
                99999,
                test_user.id,
                errors.project_not_found,
            )
        # Verify the specific error code from project_not_found
        assert "NOT_FOUND_004" in str(exc_info.value.detail)


class TestGetNextPosition:
    """Tests for get_next_position function."""

    async def test_returns_1_for_empty_table(self, db_session, test_user):
        """Should return 1 when no records exist."""
        # Delete all existing todos for this user
        result = await db_session.execute(
            select(Todo).where(Todo.user_id == test_user.id)
        )
        for todo in result.scalars().all():
            await db_session.delete(todo)
        await db_session.flush()

        position = await get_next_position(db_session, Todo, test_user.id)
        assert position == 1

    async def test_returns_next_position(self, db_session, test_user, test_todo):
        """Should return max position + 1."""
        position = await get_next_position(db_session, Todo, test_user.id)
        assert position == test_todo.position + 1

    async def test_excludes_deleted_todos(
        self, db_session, test_user, test_todo, deleted_todo
    ):
        """Should not count soft-deleted records."""
        # deleted_todo has position 2, but should be ignored
        position = await get_next_position(db_session, Todo, test_user.id)
        assert position == test_todo.position + 1

    async def test_includes_deleted_when_check_deleted_false(
        self, db_session, test_user, test_todo, deleted_todo
    ):
        """Should count deleted records when check_deleted=False."""
        position = await get_next_position(
            db_session, Todo, test_user.id, check_deleted=False
        )
        assert position == deleted_todo.position + 1

    async def test_scopes_to_parent_id(self, db_session, test_user, test_todo):
        """Should calculate position within parent scope."""
        # Create a subtask
        subtask = Todo(
            user_id=test_user.id,
            title="Subtask",
            parent_id=test_todo.id,
            priority=Priority.medium,
            status=Status.pending,
            position=1,
        )
        db_session.add(subtask)
        await db_session.flush()

        # Get next position for subtasks under this parent
        position = await get_next_position(
            db_session, Todo, test_user.id, parent_id=test_todo.id
        )
        assert position == 2

        # Root-level position should be different
        root_position = await get_next_position(db_session, Todo, test_user.id)
        assert root_position == test_todo.position + 1

    async def test_isolates_by_user(self, db_session, test_user, other_user, test_todo):
        """Should not count other user's records."""
        position = await get_next_position(db_session, Todo, other_user.id)
        assert position == 1  # Other user has no todos

    async def test_works_for_models_without_parent_id(
        self, db_session, test_user, test_project
    ):
        """Should work for models that don't have parent_id."""
        position = await get_next_position(db_session, Project, test_user.id)
        assert position == test_project.position + 1


class TestVerifyResourceExists:
    """Tests for verify_resource_exists function."""

    async def test_returns_resource_when_exists(
        self, db_session, test_user, test_project
    ):
        """Should return the resource when it exists."""
        result = await verify_resource_exists(
            db_session,
            Project,
            test_project.id,
            test_user.id,
            errors.project_not_found,
        )
        assert result.id == test_project.id

    async def test_raises_when_not_found(self, db_session, test_user):
        """Should raise error when resource doesn't exist."""
        with pytest.raises(HTTPException) as exc_info:
            await verify_resource_exists(
                db_session,
                Project,
                99999,
                test_user.id,
                errors.project_not_found,
            )
        assert exc_info.value.status_code == 404


class TestGetResourcesForUser:
    """Tests for get_resources_for_user function."""

    async def test_returns_all_matching_resources(
        self, db_session, test_user, test_todo
    ):
        """Should return all resources that match the IDs."""
        # Create additional todos
        todo2 = Todo(
            user_id=test_user.id,
            title="Todo 2",
            priority=Priority.medium,
            status=Status.pending,
            position=3,
        )
        db_session.add(todo2)
        await db_session.flush()

        result = await get_resources_for_user(
            db_session, Todo, [test_todo.id, todo2.id], test_user.id
        )

        assert len(result) == 2
        assert test_todo.id in result
        assert todo2.id in result

    async def test_returns_empty_dict_for_no_matches(self, db_session, test_user):
        """Should return empty dict when no IDs match."""
        result = await get_resources_for_user(
            db_session, Todo, [99998, 99999], test_user.id
        )
        assert result == {}

    async def test_excludes_other_users_resources(
        self, db_session, test_user, other_user, test_todo
    ):
        """Should not return resources belonging to other users."""
        result = await get_resources_for_user(
            db_session, Todo, [test_todo.id], other_user.id
        )
        assert result == {}

    async def test_returns_partial_matches(self, db_session, test_user, test_todo):
        """Should return only existing resources from the list."""
        result = await get_resources_for_user(
            db_session, Todo, [test_todo.id, 99999], test_user.id
        )
        assert len(result) == 1
        assert test_todo.id in result

    async def test_excludes_deleted_resources(
        self, db_session, test_user, test_todo, deleted_todo
    ):
        """Should not return soft-deleted resources by default."""
        result = await get_resources_for_user(
            db_session, Todo, [test_todo.id, deleted_todo.id], test_user.id
        )
        assert len(result) == 1
        assert test_todo.id in result
        assert deleted_todo.id not in result

    async def test_includes_deleted_when_check_deleted_false(
        self, db_session, test_user, test_todo, deleted_todo
    ):
        """Should return deleted resources when check_deleted=False."""
        result = await get_resources_for_user(
            db_session,
            Todo,
            [test_todo.id, deleted_todo.id],
            test_user.id,
            check_deleted=False,
        )
        assert len(result) == 2
        assert deleted_todo.id in result


class TestAuthorizationBoundaries:
    """Tests for authorization edge cases across all functions."""

    async def test_user_cannot_access_others_todo(
        self, db_session, test_user, other_user, test_todo
    ):
        """User should not be able to access another user's todo."""
        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session, Todo, test_todo.id, other_user.id, errors.todo_not_found
            )
        assert exc_info.value.status_code == 404

    async def test_user_cannot_access_others_project(
        self, db_session, test_user, other_user, test_project
    ):
        """User should not be able to access another user's project."""
        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session,
                Project,
                test_project.id,
                other_user.id,
                errors.project_not_found,
            )
        assert exc_info.value.status_code == 404

    async def test_bulk_fetch_respects_user_boundaries(
        self, db_session, test_user, other_user, test_todo
    ):
        """Bulk fetch should only return resources for the specified user."""
        # Create a todo for other_user
        other_todo = Todo(
            user_id=other_user.id,
            title="Other User Todo",
            priority=Priority.medium,
            status=Status.pending,
            position=1,
        )
        db_session.add(other_todo)
        await db_session.flush()

        # test_user should only see their own todo
        result = await get_resources_for_user(
            db_session, Todo, [test_todo.id, other_todo.id], test_user.id
        )
        assert len(result) == 1
        assert test_todo.id in result
        assert other_todo.id not in result


class TestSoftDeleteBehavior:
    """Tests for soft-delete handling across all functions."""

    async def test_recently_deleted_todo_not_found(
        self, db_session, test_user, test_todo
    ):
        """A todo deleted just now should not be found."""
        test_todo.deleted_at = datetime.now(UTC)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session, Todo, test_todo.id, test_user.id, errors.todo_not_found
            )
        assert exc_info.value.status_code == 404

    async def test_deleted_long_ago_todo_not_found(
        self, db_session, test_user, test_todo
    ):
        """A todo deleted long ago should not be found."""
        test_todo.deleted_at = datetime.now(UTC) - timedelta(days=30)
        await db_session.flush()

        with pytest.raises(HTTPException) as exc_info:
            await get_resource_for_user(
                db_session, Todo, test_todo.id, test_user.id, errors.todo_not_found
            )
        assert exc_info.value.status_code == 404

    async def test_position_calculation_ignores_deleted(self, db_session, test_user):
        """Position calculation should ignore deleted records."""
        # Create todos with positions 1, 2, 3
        for i in range(1, 4):
            todo = Todo(
                user_id=test_user.id,
                title=f"Todo {i}",
                priority=Priority.medium,
                status=Status.pending,
                position=i,
                deleted_at=datetime.now(UTC) if i == 3 else None,
            )
            db_session.add(todo)
        await db_session.flush()

        # Should return 3, not 4 (ignoring deleted todo with position 3)
        position = await get_next_position(db_session, Todo, test_user.id)
        assert position == 3
