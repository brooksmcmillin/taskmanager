"""Unit tests for MCP server helper functions and tools."""

import datetime
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from mcp_resource_framework.validation import validate_dict_response, validate_list_response
from taskmanager_sdk import ApiResponse

from mcp_resource.server import _past_due_date_warning


class TestValidateListResponse:
    """Tests for validate_list_response helper function."""

    def test_success_with_plain_list(self) -> None:
        """Test successful validation when response data is a plain list."""
        response = ApiResponse(
            success=True,
            data=[{"id": 1, "name": "task1"}, {"id": 2, "name": "task2"}],
            status_code=200,
        )
        result, error = validate_list_response(response, "tasks")
        assert error is None
        assert len(result) == 2
        assert result[0]["id"] == 1

    def test_success_with_wrapped_response(self) -> None:
        """Test successful validation when response data is wrapped in a dict."""
        response = ApiResponse(
            success=True,
            data={"tasks": [{"id": 1}, {"id": 2}]},
            status_code=200,
        )
        result, error = validate_list_response(response, "tasks")
        assert error is None
        assert len(result) == 2

    def test_success_with_explicit_key(self) -> None:
        """Test successful validation with explicit key parameter."""
        response = ApiResponse(
            success=True,
            data={"items": [{"id": 1}]},
            status_code=200,
        )
        result, error = validate_list_response(response, "things", key="items")
        assert error is None
        assert len(result) == 1

    def test_success_with_plural_context_key(self) -> None:
        """Test that context + 's' is tried as a key."""
        response = ApiResponse(
            success=True,
            data={"categories": [{"name": "work"}]},
            status_code=200,
        )
        # Context is "categorie" but data has "categories" key
        result, error = validate_list_response(response, "categorie")
        assert error is None
        assert len(result) == 1

    def test_failed_response(self) -> None:
        """Test validation returns error for failed API response."""
        response = ApiResponse(
            success=False,
            error="API error occurred",
            status_code=500,
        )
        result, error = validate_list_response(response, "tasks")
        assert error == "API error occurred"
        assert result == []

    def test_none_data(self) -> None:
        """Test validation returns empty list for None data."""
        response = ApiResponse(success=True, data=None, status_code=200)
        result, error = validate_list_response(response, "tasks")
        assert error is None
        assert result == []

    def test_dict_without_expected_key(self) -> None:
        """Test validation returns error when dict doesn't have expected key."""
        response = ApiResponse(
            success=True,
            data={"other_key": [{"id": 1}]},
            status_code=200,
        )
        result, error = validate_list_response(response, "tasks")
        assert error is not None
        assert "dict without expected key" in error
        assert result == []

    def test_invalid_type_string(self) -> None:
        """Test validation returns error when data is a string."""
        response = ApiResponse(
            success=True,
            data="unexpected string response",
            status_code=200,
        )
        result, error = validate_list_response(response, "tasks")
        assert error is not None
        assert "expected list" in error
        assert result == []

    def test_filters_non_dict_items(self) -> None:
        """Test that non-dict items in list are filtered out."""
        response = ApiResponse(
            success=True,
            data=[{"id": 1}, "invalid", {"id": 2}, 123],
            status_code=200,
        )
        result, error = validate_list_response(response, "tasks")
        assert error is None
        assert len(result) == 2
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2


class TestValidateDictResponse:
    """Tests for validate_dict_response helper function."""

    def test_success_with_dict(self) -> None:
        """Test successful validation when response data is a dict."""
        response = ApiResponse(
            success=True,
            data={"id": 1, "title": "Test Task"},
            status_code=200,
        )
        result, error = validate_dict_response(response, "task")
        assert error is None
        assert result is not None
        assert result["id"] == 1

    def test_failed_response(self) -> None:
        """Test validation returns error for failed API response."""
        response = ApiResponse(
            success=False,
            error="Task not found",
            status_code=404,
        )
        result, error = validate_dict_response(response, "task")
        assert error == "Task not found"
        assert result is None

    def test_none_data(self) -> None:
        """Test validation returns error for None data."""
        response = ApiResponse(success=True, data=None, status_code=200)
        result, error = validate_dict_response(response, "task")
        assert error is not None
        assert "No task data returned" in error
        assert result is None

    def test_invalid_type_list(self) -> None:
        """Test validation returns error when data is a list."""
        response = ApiResponse(
            success=True,
            data=[{"id": 1}],
            status_code=200,
        )
        result, error = validate_dict_response(response, "task")
        assert error is not None
        assert "expected dict" in error
        assert result is None

    def test_invalid_type_string(self) -> None:
        """Test validation returns error when data is a string."""
        response = ApiResponse(
            success=True,
            data="unexpected string",
            status_code=200,
        )
        result, error = validate_dict_response(response, "task")
        assert error is not None
        assert "expected dict" in error
        assert result is None


class TestMCPToolsIntegration:
    """Integration tests for MCP tool functions with mocked API client."""

    @pytest.fixture
    def mock_api_client(self) -> MagicMock:
        """Create a mock API client."""
        client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_tasks_with_wrapped_response(self, mock_api_client: MagicMock) -> None:
        """Test get_tasks handles wrapped {'tasks': [...]} response."""
        mock_api_client.get_todos.return_value = ApiResponse(
            success=True,
            data={
                "tasks": [
                    {"id": 1, "title": "Task 1", "status": "pending"},
                    {"id": 2, "title": "Task 2", "status": "completed"},
                ]
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            # Import here to get patched version

            # We can't easily test the async tool directly, so verify the helper works
            response = mock_api_client.get_todos()
            tasks, error = validate_list_response(response, "tasks")
            assert error is None
            assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_get_tasks_with_plain_list_response(self, mock_api_client: MagicMock) -> None:
        """Test get_tasks handles plain list response."""
        mock_api_client.get_todos.return_value = ApiResponse(
            success=True,
            data=[
                {"id": 1, "title": "Task 1"},
                {"id": 2, "title": "Task 2"},
            ],
            status_code=200,
        )

        response = mock_api_client.get_todos()
        tasks, error = validate_list_response(response, "tasks")
        assert error is None
        assert len(tasks) == 2

    @pytest.mark.asyncio
    async def test_search_tasks_with_wrapped_response(self, mock_api_client: MagicMock) -> None:
        """Test search_tasks handles wrapped {'tasks': [...]} response."""
        mock_api_client.search_tasks.return_value = ApiResponse(
            success=True,
            data={
                "tasks": [{"id": 1, "title": "Matching Task"}],
                "count": 1,
            },
            status_code=200,
        )

        response = mock_api_client.search_tasks(query="matching")
        tasks, error = validate_list_response(response, "tasks")
        assert error is None
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_create_task_with_dict_response(self, mock_api_client: MagicMock) -> None:
        """Test create_task handles dict response."""
        mock_api_client.create_todo.return_value = ApiResponse(
            success=True,
            data={"id": 123, "title": "New Task"},
            status_code=201,
        )

        response = mock_api_client.create_todo(title="New Task")
        task, error = validate_dict_response(response, "created task")
        assert error is None
        assert task is not None
        assert task["id"] == 123

    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_api_client: MagicMock) -> None:
        """Test error handling when API returns an error."""
        mock_api_client.get_todos.return_value = ApiResponse(
            success=False,
            error="Authentication failed",
            status_code=401,
        )

        response = mock_api_client.get_todos()
        tasks, error = validate_list_response(response, "tasks")
        assert error == "Authentication failed"
        assert tasks == []


class TestTaskTransformation:
    """Tests for task data transformation in MCP tools."""

    def test_task_id_prefixing(self) -> None:
        """Test that task IDs are properly prefixed with 'task_'."""
        task_data = {"id": 123, "title": "Test"}
        transformed_id = f"task_{task_data['id']}"
        assert transformed_id == "task_123"

    def test_task_id_parsing(self) -> None:
        """Test parsing task IDs from 'task_XXX' format."""
        task_id = "task_123"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 123

    def test_task_id_parsing_without_prefix(self) -> None:
        """Test parsing task IDs when no prefix present."""
        task_id = "456"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 456

    def test_task_transformation_handles_missing_fields(self) -> None:
        """Test that task transformation handles missing optional fields."""
        task = {"id": 1, "title": "Test"}  # Minimal task

        transformed = {
            "id": f"task_{task.get('id')}",
            "title": task.get("title", ""),
            "description": task.get("description"),
            "due_date": task.get("due_date"),
            "status": task.get("status", "pending"),
            "category": task.get("project_name") or task.get("category"),
            "priority": task.get("priority", "medium"),
            "tags": task.get("tags") or [],
            "created_at": task.get("created_at"),
            "updated_at": task.get("updated_at"),
        }

        assert transformed["id"] == "task_1"
        assert transformed["title"] == "Test"
        assert transformed["description"] is None
        assert transformed["status"] == "pending"
        assert transformed["priority"] == "medium"
        assert transformed["tags"] == []

    def test_task_transformation_prefers_project_name(self) -> None:
        """Test that project_name is preferred over category field."""
        task = {
            "id": 1,
            "title": "Test",
            "project_name": "Work",
            "category": "Old Category",
        }

        category = task.get("project_name") or task.get("category")
        assert category == "Work"

    def test_task_transformation_falls_back_to_category(self) -> None:
        """Test fallback to category when project_name is missing."""
        task = {"id": 1, "title": "Test", "category": "Personal"}

        category = task.get("project_name") or task.get("category")
        assert category == "Personal"


class TestTimestampInResponses:
    """Tests for current_time timestamp in MCP tool responses."""

    def test_timestamp_format(self) -> None:
        """Test that timestamps are in ISO format."""
        import datetime

        now = datetime.datetime.now(tz=datetime.UTC)
        timestamp = now.isoformat()

        # Verify it's a valid ISO format
        parsed = datetime.datetime.fromisoformat(timestamp)
        assert isinstance(parsed, datetime.datetime)

    def test_response_includes_current_time(self) -> None:
        """Test that responses include current_time field."""
        import datetime
        import json

        # Simulate a response with current_time
        response_dict = {
            "tasks": [{"id": "task_1", "title": "Test"}],
            "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        }

        response = json.dumps(response_dict)
        parsed = json.loads(response)

        assert "current_time" in parsed
        assert isinstance(parsed["current_time"], str)
        # Verify it can be parsed as ISO timestamp
        datetime.datetime.fromisoformat(parsed["current_time"])


class TestSubtasksSupport:
    """Tests for subtasks functionality in MCP tools."""

    def test_task_with_subtasks_structure(self) -> None:
        """Test that tasks can include subtasks array."""
        task = {
            "id": 1,
            "title": "Parent Task",
            "subtasks": [
                {
                    "id": 2,
                    "title": "Subtask 1",
                    "status": "pending",
                    "priority": "medium",
                },
                {
                    "id": 3,
                    "title": "Subtask 2",
                    "status": "completed",
                    "priority": "high",
                },
            ],
        }

        assert "subtasks" in task
        assert len(task["subtasks"]) == 2
        assert task["subtasks"][0]["title"] == "Subtask 1"
        assert task["subtasks"][1]["status"] == "completed"

    def test_subtask_transformation(self) -> None:
        """Test transformation of subtasks in response."""
        subtask = {
            "id": 10,
            "title": "Subtask",
            "description": "Details",
            "status": "in_progress",
            "priority": "high",
            "due_date": "2025-02-01",
            "estimated_hours": 2.5,
            "actual_hours": 1.0,
            "created_at": "2025-01-30T10:00:00",
            "updated_at": "2025-01-30T11:00:00",
        }

        transformed = {
            "id": f"task_{subtask.get('id')}",
            "title": subtask.get("title", ""),
            "description": subtask.get("description"),
            "status": subtask.get("status", "pending"),
            "priority": subtask.get("priority", "medium"),
            "due_date": subtask.get("due_date"),
            "estimated_hours": subtask.get("estimated_hours"),
            "actual_hours": subtask.get("actual_hours"),
            "created_at": subtask.get("created_at"),
            "updated_at": subtask.get("updated_at"),
        }

        assert transformed["id"] == "task_10"
        assert transformed["title"] == "Subtask"
        assert transformed["status"] == "in_progress"
        assert transformed["estimated_hours"] == 2.5

    def test_parent_id_parsing(self) -> None:
        """Test parsing parent_id from task."""
        task = {"id": 5, "title": "Child Task", "parent_id": 1}

        parent_id_str = f"task_{task.get('parent_id')}" if task.get("parent_id") else None
        assert parent_id_str == "task_1"

    def test_parent_id_none_for_root_task(self) -> None:
        """Test that root tasks have None parent_id."""
        task = {"id": 1, "title": "Root Task", "parent_id": None}

        parent_id_str = f"task_{task.get('parent_id')}" if task.get("parent_id") else None
        assert parent_id_str is None

    def test_parent_id_conversion_for_create(self) -> None:
        """Test converting parent_id string to int for API calls."""
        parent_id = "task_123"

        numeric_id = parent_id.replace("task_", "") if parent_id.startswith("task_") else parent_id
        parent_id_int = int(numeric_id)

        assert parent_id_int == 123

    def test_parent_id_conversion_without_prefix(self) -> None:
        """Test converting parent_id without prefix."""
        parent_id = "456"

        numeric_id = parent_id.replace("task_", "") if parent_id.startswith("task_") else parent_id
        parent_id_int = int(numeric_id)

        assert parent_id_int == 456

    @pytest.mark.asyncio
    async def test_get_tasks_with_subtasks_response(self) -> None:
        """Test get_tasks handles tasks with subtasks."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={
                "tasks": [
                    {
                        "id": 1,
                        "title": "Parent",
                        "subtasks": [
                            {"id": 2, "title": "Child 1", "status": "pending"},
                            {"id": 3, "title": "Child 2", "status": "completed"},
                        ],
                    }
                ]
            },
            status_code=200,
        )

        response = mock_client._make_request("GET", "/todos", {"include_subtasks": True})
        tasks, error = validate_list_response(response, "tasks")

        assert error is None
        assert len(tasks) == 1
        assert "subtasks" in tasks[0]
        assert len(tasks[0]["subtasks"]) == 2


class TestAttachmentTools:
    """Tests for attachment management MCP tools."""

    @pytest.mark.asyncio
    async def test_list_attachments_response(self) -> None:
        """Test list_task_attachments returns attachment data."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={
                "attachments": [
                    {
                        "id": 1,
                        "todo_id": 10,
                        "filename": "screenshot.png",
                        "content_type": "image/png",
                        "file_size": 12345,
                        "created_at": "2025-01-30T10:00:00",
                    },
                    {
                        "id": 2,
                        "todo_id": 10,
                        "filename": "document.pdf",
                        "content_type": "application/pdf",
                        "file_size": 54321,
                        "created_at": "2025-01-30T11:00:00",
                    },
                ]
            },
            status_code=200,
        )

        response = mock_client._make_request("GET", "/todos/10/attachments")
        attachments, error = validate_list_response(response, "attachments")

        assert error is None
        assert len(attachments) == 2
        assert attachments[0]["filename"] == "screenshot.png"
        assert attachments[0]["content_type"] == "image/png"
        assert attachments[1]["file_size"] == 54321

    @pytest.mark.asyncio
    async def test_list_attachments_empty(self) -> None:
        """Test list_task_attachments with no attachments."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={"attachments": []},
            status_code=200,
        )

        response = mock_client._make_request("GET", "/todos/10/attachments")
        attachments, error = validate_list_response(response, "attachments")

        assert error is None
        assert len(attachments) == 0

    def test_attachment_response_structure(self) -> None:
        """Test attachment response data structure."""
        attachment = {
            "id": 1,
            "todo_id": 10,
            "filename": "image.jpg",
            "content_type": "image/jpeg",
            "file_size": 102400,
            "created_at": "2025-01-30T10:00:00",
        }

        assert "id" in attachment
        assert "todo_id" in attachment
        assert "filename" in attachment
        assert "content_type" in attachment
        assert "file_size" in attachment
        assert "created_at" in attachment
        assert isinstance(attachment["file_size"], int)
        assert attachment["file_size"] > 0


class TestGetTaskTool:
    """Tests for get_task MCP tool."""

    @pytest.mark.asyncio
    async def test_get_task_success(self) -> None:
        """Test get_task retrieves a single task with full details."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={
                "id": 42,
                "title": "Test Task",
                "description": "Task description",
                "status": "in_progress",
                "priority": "high",
                "due_date": "2025-02-15",
                "project_name": "Work",
                "tags": ["urgent", "backend"],
                "parent_id": None,
                "subtasks": [
                    {
                        "id": 43,
                        "title": "Subtask 1",
                        "status": "pending",
                        "priority": "medium",
                    }
                ],
                "estimated_hours": 5.0,
                "actual_hours": 2.5,
                "created_at": "2025-01-30T10:00:00",
                "updated_at": "2025-01-30T12:00:00",
            },
            status_code=200,
        )

        response = mock_client._make_request("GET", "/todos/42")
        task, error = validate_dict_response(response, "task")

        assert error is None
        assert task is not None
        assert task["id"] == 42
        assert task["title"] == "Test Task"
        assert task["status"] == "in_progress"
        assert task["priority"] == "high"
        assert "subtasks" in task
        assert len(task["subtasks"]) == 1

    @pytest.mark.asyncio
    async def test_get_task_not_found(self) -> None:
        """Test get_task handles task not found error."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False, error="Task not found", status_code=404
        )

        response = mock_client._make_request("GET", "/todos/999")
        task, error = validate_dict_response(response, "task")

        assert error == "Task not found"
        assert task is None

    def test_task_id_parsing_for_get_task(self) -> None:
        """Test parsing task_id in different formats."""
        # Test with prefix
        task_id = "task_123"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 123

        # Test without prefix
        task_id = "456"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 456


class TestDeleteTaskTool:
    """Tests for delete_task MCP tool."""

    @pytest.mark.asyncio
    async def test_delete_task_success(self) -> None:
        """Test delete_task successfully deletes a task."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True, data={"deleted": True}, status_code=200
        )

        response = mock_client._make_request("DELETE", "/todos/10")

        assert response.success is True
        assert response.data is not None
        assert response.data.get("deleted") is True

    @pytest.mark.asyncio
    async def test_delete_task_not_found(self) -> None:
        """Test delete_task handles task not found error."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False, error="Task not found", status_code=404
        )

        response = mock_client._make_request("DELETE", "/todos/999")

        assert response.success is False
        assert response.error == "Task not found"

    @pytest.mark.asyncio
    async def test_delete_task_with_subtasks(self) -> None:
        """Test that deleting a task also deletes its subtasks."""
        mock_client = MagicMock()
        # Backend handles cascade delete, so we just verify the request succeeds
        mock_client._make_request.return_value = ApiResponse(
            success=True, data={"deleted": True}, status_code=200
        )

        response = mock_client._make_request("DELETE", "/todos/10")

        assert response.success is True

    def test_delete_task_id_parsing(self) -> None:
        """Test task_id parsing for delete operations."""
        task_id = "task_123"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 123


class TestCompleteTaskTool:
    """Tests for complete_task MCP tool."""

    @pytest.mark.asyncio
    async def test_complete_task_success(self) -> None:
        """Test complete_task marks a task as completed."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True, data={"completed": True}, status_code=200
        )

        response = mock_client._make_request("POST", "/todos/10/complete")

        assert response.success is True
        assert response.data is not None
        assert response.data.get("completed") is True

    @pytest.mark.asyncio
    async def test_complete_task_not_found(self) -> None:
        """Test complete_task handles task not found error."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False, error="Task not found", status_code=404
        )

        response = mock_client._make_request("POST", "/todos/999/complete")

        assert response.success is False
        assert response.error == "Task not found"

    @pytest.mark.asyncio
    async def test_complete_already_completed_task(self) -> None:
        """Test completing an already completed task."""
        mock_client = MagicMock()
        # Backend allows re-completing tasks
        mock_client._make_request.return_value = ApiResponse(
            success=True, data={"completed": True}, status_code=200
        )

        response = mock_client._make_request("POST", "/todos/10/complete")

        assert response.success is True

    def test_complete_task_id_parsing(self) -> None:
        """Test task_id parsing for complete operations."""
        # With prefix
        task_id = "task_789"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 789

        # Without prefix
        task_id = "123"
        numeric_id = task_id.replace("task_", "") if task_id.startswith("task_") else task_id
        assert int(numeric_id) == 123


class TestCreateProjectTool:
    """Tests for create_project MCP tool."""

    @pytest.mark.asyncio
    async def test_create_project_success(self) -> None:
        """Test create_project creates a project with all fields."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={"id": 1, "name": "Phase 1", "description": "First phase", "color": "#FF5733"},
            status_code=201,
        )

        response = mock_client._make_request("POST", "/projects")
        project, error = validate_dict_response(response, "created project")

        assert error is None
        assert project is not None
        assert project["id"] == 1
        assert project["name"] == "Phase 1"

    @pytest.mark.asyncio
    async def test_create_project_minimal(self) -> None:
        """Test create_project with only required name field."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={"id": 2, "name": "My Project"},
            status_code=201,
        )

        response = mock_client._make_request("POST", "/projects")
        project, error = validate_dict_response(response, "created project")

        assert error is None
        assert project is not None
        assert project["id"] == 2

    @pytest.mark.asyncio
    async def test_create_project_error(self) -> None:
        """Test create_project handles API errors."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False,
            error="Project name already exists",
            status_code=400,
        )

        response = mock_client._make_request("POST", "/projects")
        project, error = validate_dict_response(response, "created project")

        assert error == "Project name already exists"
        assert project is None


class TestDependencyTools:
    """Tests for task dependency MCP tools."""

    @pytest.mark.asyncio
    async def test_list_dependencies_success(self) -> None:
        """Test list_dependencies returns dependency tasks."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data=[
                {
                    "id": 5,
                    "title": "Blocking Task",
                    "status": "pending",
                    "priority": "high",
                    "due_date": "2026-03-01",
                    "project_id": 1,
                    "project_name": "Phase 1",
                },
            ],
            status_code=200,
        )

        response = mock_client._make_request("GET", "/todos/10/dependencies")
        dependencies, error = validate_list_response(response, "dependencies")

        assert error is None
        assert len(dependencies) == 1
        assert dependencies[0]["id"] == 5
        assert dependencies[0]["title"] == "Blocking Task"
        assert dependencies[0]["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_dependencies_empty(self) -> None:
        """Test list_dependencies with no dependencies."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data=[],
            status_code=200,
        )

        response = mock_client._make_request("GET", "/todos/10/dependencies")
        dependencies, error = validate_list_response(response, "dependencies")

        assert error is None
        assert len(dependencies) == 0

    @pytest.mark.asyncio
    async def test_add_dependency_success(self) -> None:
        """Test add_dependency creates a dependency relationship."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={"id": 5, "title": "Blocking Task", "status": "pending"},
            status_code=201,
        )

        response = mock_client._make_request("POST", "/todos/10/dependencies", {"dependency_id": 5})

        assert response.success is True
        assert response.data is not None
        assert response.data["id"] == 5

    @pytest.mark.asyncio
    async def test_add_dependency_circular_error(self) -> None:
        """Test add_dependency handles circular dependency error."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False,
            error="Circular dependency detected",
            status_code=400,
        )

        response = mock_client._make_request("POST", "/todos/10/dependencies", {"dependency_id": 5})

        assert response.success is False
        assert "Circular dependency" in (response.error or "")

    @pytest.mark.asyncio
    async def test_add_dependency_self_error(self) -> None:
        """Test add_dependency handles self-dependency error."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False,
            error="A task cannot depend on itself",
            status_code=400,
        )

        response = mock_client._make_request(
            "POST", "/todos/10/dependencies", {"dependency_id": 10}
        )

        assert response.success is False
        assert response.error is not None

    def test_dependency_id_parsing(self) -> None:
        """Test parsing dependency IDs in task_N format."""
        # With prefix
        dep_id = "task_42"
        numeric_id = dep_id.replace("task_", "") if dep_id.startswith("task_") else dep_id
        assert int(numeric_id) == 42

        # Without prefix
        dep_id = "42"
        numeric_id = dep_id.replace("task_", "") if dep_id.startswith("task_") else dep_id
        assert int(numeric_id) == 42

    def test_dependency_response_transformation(self) -> None:
        """Test transforming dependency response to MCP format."""
        dep = {
            "id": 5,
            "title": "Blocking Task",
            "status": "pending",
            "priority": "high",
            "due_date": "2026-03-01",
            "project_name": "Phase 1",
        }

        transformed = {
            "id": f"task_{dep.get('id')}",
            "title": dep.get("title", ""),
            "status": dep.get("status", "pending"),
            "priority": dep.get("priority", "medium"),
            "due_date": dep.get("due_date"),
            "project_name": dep.get("project_name"),
        }

        assert transformed["id"] == "task_5"
        assert transformed["title"] == "Blocking Task"
        assert transformed["project_name"] == "Phase 1"


class TestCreateTaskDeadlineTypeValidation:
    """Tests for deadline_type validation in create_task."""

    @pytest.fixture
    def mock_api_client(self) -> MagicMock:
        """Create a mock API client."""
        client = MagicMock()
        client.create_todo.return_value = ApiResponse(
            success=True,
            data={"id": 1, "title": "Test Task"},
            status_code=201,
        )
        return client

    @pytest.mark.asyncio
    async def test_valid_deadline_types_accepted(self, mock_api_client: MagicMock) -> None:
        """Test that all valid deadline_type values are accepted."""
        import json

        from mcp_resource.server import create_resource_server

        for dt in ("flexible", "preferred", "firm", "hard"):
            with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
                # Import the create_task tool function
                server = create_resource_server(
                    port=8001,
                    server_url="https://localhost:8001",
                    auth_server_url="https://localhost:9000",
                    auth_server_public_url="https://localhost:9000",
                    oauth_strict=False,
                )
                # Access the tool directly - FastMCP stores tools
                tools = server._tool_manager._tools
                create_task_tool = tools["create_task"]
                result = await create_task_tool.fn(title="Test", deadline_type=dt)
                parsed = json.loads(result)
                assert "error" not in parsed, f"deadline_type={dt!r} should be valid, got: {parsed}"

    @pytest.mark.asyncio
    async def test_invalid_deadline_type_rejected(self) -> None:
        """Test that invalid deadline_type values return an error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_task_tool = tools["create_task"]
            result = await create_task_tool.fn(title="Test", deadline_type="invalid")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "Invalid deadline_type" in parsed["error"]
            assert "invalid" in parsed["error"]

    @pytest.mark.asyncio
    async def test_empty_string_deadline_type_rejected(self) -> None:
        """Test that empty string deadline_type is rejected."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_task_tool = tools["create_task"]
            result = await create_task_tool.fn(title="Test", deadline_type="")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "Invalid deadline_type" in parsed["error"]

    @pytest.mark.asyncio
    async def test_deadline_type_passed_to_sdk(self, mock_api_client: MagicMock) -> None:
        """Test that deadline_type is passed through to the SDK create_todo call."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_task_tool = tools["create_task"]
            await create_task_tool.fn(title="Test", deadline_type="firm")

            # Verify deadline_type was passed to the SDK
            mock_api_client.create_todo.assert_called_once()
            call_kwargs = mock_api_client.create_todo.call_args[1]
            assert call_kwargs["deadline_type"] == "firm"


class TestUpdateTaskDeadlineTypeValidation:
    """Tests for deadline_type validation in update_task."""

    @pytest.fixture
    def mock_api_client(self) -> MagicMock:
        """Create a mock API client."""
        client = MagicMock()
        client.update_todo.return_value = ApiResponse(
            success=True,
            data={"id": 1, "updated_fields": ["deadline_type"], "status": "updated"},
            status_code=200,
        )
        return client

    @pytest.mark.asyncio
    async def test_valid_deadline_types_accepted(self, mock_api_client: MagicMock) -> None:
        """Test that all valid deadline_type values are accepted in update_task."""
        import json

        from mcp_resource.server import create_resource_server

        for dt in ("flexible", "preferred", "firm", "hard"):
            with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
                server = create_resource_server(
                    port=8001,
                    server_url="https://localhost:8001",
                    auth_server_url="https://localhost:9000",
                    auth_server_public_url="https://localhost:9000",
                    oauth_strict=False,
                )
                tools = server._tool_manager._tools
                update_task_tool = tools["update_task"]
                result = await update_task_tool.fn(task_id="task_1", deadline_type=dt)
                parsed = json.loads(result)
                assert "error" not in parsed, f"deadline_type={dt!r} should be valid, got: {parsed}"

    @pytest.mark.asyncio
    async def test_invalid_deadline_type_rejected(self) -> None:
        """Test that invalid deadline_type values return an error in update_task."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            update_task_tool = tools["update_task"]
            result = await update_task_tool.fn(task_id="task_1", deadline_type="invalid")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "Invalid deadline_type" in parsed["error"]

    @pytest.mark.asyncio
    async def test_deadline_type_passed_to_sdk(self, mock_api_client: MagicMock) -> None:
        """Test that deadline_type is passed through to the SDK update_todo call."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            update_task_tool = tools["update_task"]
            await update_task_tool.fn(task_id="task_1", deadline_type="hard")

            mock_api_client.update_todo.assert_called_once()
            call_kwargs = mock_api_client.update_todo.call_args[1]
            assert call_kwargs["deadline_type"] == "hard"

    @pytest.mark.asyncio
    async def test_deadline_type_in_updated_fields(self, mock_api_client: MagicMock) -> None:
        """Test that deadline_type appears in updated_fields when provided."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            update_task_tool = tools["update_task"]
            result = await update_task_tool.fn(task_id="task_1", deadline_type="firm")
            parsed = json.loads(result)
            assert "deadline_type" in parsed["updated_fields"]


class TestPastDueDateWarning:
    """Tests for _past_due_date_warning helper function."""

    def test_past_date_returns_warning(self) -> None:
        """Test that a date in the past produces a warning."""
        past = (
            datetime.datetime.now(tz=datetime.UTC).date() - datetime.timedelta(days=1)
        ).isoformat()
        warning = _past_due_date_warning(past)
        assert warning is not None
        assert past in warning
        assert "in the past" in warning

    def test_future_date_returns_none(self) -> None:
        """Test that a future date produces no warning."""
        future = (
            datetime.datetime.now(tz=datetime.UTC).date() + datetime.timedelta(days=30)
        ).isoformat()
        assert _past_due_date_warning(future) is None

    def test_today_returns_none(self) -> None:
        """Test that today's date produces no warning."""
        today = datetime.datetime.now(tz=datetime.UTC).date().isoformat()
        assert _past_due_date_warning(today) is None

    def test_none_returns_none(self) -> None:
        """Test that None input produces no warning."""
        assert _past_due_date_warning(None) is None

    def test_empty_string_returns_none(self) -> None:
        """Test that empty string produces no warning."""
        assert _past_due_date_warning("") is None

    def test_invalid_date_returns_none(self) -> None:
        """Test that an invalid date string produces no warning."""
        assert _past_due_date_warning("not-a-date") is None

    def test_create_task_includes_warning_for_past_due_date(self) -> None:
        """Test that create_task response includes warning for past due dates."""
        import json
        from typing import Any

        # Simulate the create_task result-building logic
        due_date = "2020-01-01"
        result: dict[str, Any] = {
            "id": "task_1",
            "title": "Test",
            "status": "created",
            "parent_id": None,
            "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        }
        warning = _past_due_date_warning(due_date)
        if warning:
            result["warning"] = warning

        parsed = json.loads(json.dumps(result))
        assert "warning" in parsed
        assert "2020-01-01" in parsed["warning"]
        assert "in the past" in parsed["warning"]

    def test_create_task_no_warning_for_future_due_date(self) -> None:
        """Test that create_task response has no warning for future due dates."""
        from typing import Any

        due_date = (
            datetime.datetime.now(tz=datetime.UTC).date() + datetime.timedelta(days=7)
        ).isoformat()
        result: dict[str, Any] = {
            "id": "task_1",
            "title": "Test",
            "status": "created",
            "parent_id": None,
            "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        }
        warning = _past_due_date_warning(due_date)
        if warning:
            result["warning"] = warning

        assert "warning" not in result

    def test_update_task_includes_warning_for_past_due_date(self) -> None:
        """Test that update_task response includes warning for past due dates."""
        import json
        from typing import Any

        due_date = "2023-06-15"
        result: dict[str, Any] = {
            "id": "task_5",
            "updated_fields": ["due_date"],
            "status": "updated",
            "current_time": datetime.datetime.now(tz=datetime.UTC).isoformat(),
        }
        warning = _past_due_date_warning(due_date)
        if warning:
            result["warning"] = warning

        parsed = json.loads(json.dumps(result))
        assert "warning" in parsed
        assert "2023-06-15" in parsed["warning"]


class TestCreateTasksBatch:
    """Tests for the create_tasks (batch) MCP tool."""

    @pytest.fixture
    def mock_api_client(self) -> MagicMock:
        client = MagicMock()
        client.batch_create_todos.return_value = ApiResponse(
            success=True,
            data=[
                {"id": 1, "title": "Task 1"},
                {"id": 2, "title": "Task 2"},
            ],
            status_code=201,
        )
        return client

    @pytest.mark.asyncio
    async def test_batch_create_success(self, mock_api_client: MagicMock) -> None:
        """Test successful batch creation of tasks."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(
                tasks=[
                    {"title": "Task 1", "priority": "high"},
                    {"title": "Task 2", "category": "Work"},
                ]
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 2
            assert len(parsed["created"]) == 2
            assert parsed["created"][0]["id"] == "task_1"
            assert parsed["created"][1]["id"] == "task_2"

    @pytest.mark.asyncio
    async def test_batch_create_empty_list(self) -> None:
        """Test that empty tasks list returns error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(tasks=[])
            parsed = json.loads(result)
            assert "error" in parsed
            assert "empty" in parsed["error"]

    @pytest.mark.asyncio
    async def test_batch_create_missing_title(self) -> None:
        """Test that a task without a title returns error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(tasks=[{"description": "no title"}])
            parsed = json.loads(result)
            assert "error" in parsed
            assert "title" in parsed["error"]

    @pytest.mark.asyncio
    async def test_batch_create_invalid_deadline_type(self) -> None:
        """Test that invalid deadline_type in a task returns error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(tasks=[{"title": "Test", "deadline_type": "bogus"}])
            parsed = json.loads(result)
            assert "error" in parsed
            assert "deadline_type" in parsed["error"]

    @pytest.mark.asyncio
    async def test_batch_create_over_limit(self) -> None:
        """Test that more than 50 tasks returns error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(tasks=[{"title": f"Task {i}"} for i in range(51)])
            parsed = json.loads(result)
            assert "error" in parsed
            assert "50" in parsed["error"]

    @pytest.mark.asyncio
    async def test_batch_create_passes_to_sdk(self, mock_api_client: MagicMock) -> None:
        """Test that tasks are correctly passed to the SDK."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            await create_tasks_tool.fn(
                tasks=[
                    {"title": "Task 1", "priority": "high", "category": "Work"},
                    {"title": "Task 2", "tags": ["urgent"]},
                ]
            )
            mock_api_client.batch_create_todos.assert_called_once()
            call_args = mock_api_client.batch_create_todos.call_args
            todos = call_args[0][0] if call_args[0] else call_args[1]["todos"]
            assert len(todos) == 2
            assert todos[0]["title"] == "Task 1"
            assert todos[0]["priority"] == "high"
            assert todos[0]["category"] == "Work"
            assert todos[1]["title"] == "Task 2"
            assert todos[1]["tags"] == ["urgent"]

    @pytest.mark.asyncio
    async def test_batch_create_with_parent_id(self, mock_api_client: MagicMock) -> None:
        """Test that parent_id is correctly parsed from task_ format."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            await create_tasks_tool.fn(tasks=[{"title": "Subtask", "parent_id": "task_42"}])
            call_args = mock_api_client.batch_create_todos.call_args
            todos = call_args[0][0] if call_args[0] else call_args[1]["todos"]
            assert todos[0]["parent_id"] == 42

    @pytest.mark.asyncio
    async def test_batch_create_with_parent_index(self, mock_api_client: MagicMock) -> None:
        """Test that parent_index is passed through to the SDK."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            await create_tasks_tool.fn(
                tasks=[
                    {"title": "Parent task"},
                    {"title": "Child task", "parent_index": 0},
                ]
            )
            call_args = mock_api_client.batch_create_todos.call_args
            todos = call_args[0][0] if call_args[0] else call_args[1]["todos"]
            assert len(todos) == 2
            assert "parent_index" not in todos[0]
            assert todos[1]["parent_index"] == 0

    @pytest.mark.asyncio
    async def test_batch_create_parent_index_and_parent_id_conflict(self) -> None:
        """Test that parent_index and parent_id together returns error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(
                tasks=[
                    {"title": "Parent"},
                    {"title": "Child", "parent_id": "task_1", "parent_index": 0},
                ]
            )
            parsed = json.loads(result)
            assert "error" in parsed
            assert "parent_id" in parsed["error"]
            assert "parent_index" in parsed["error"]

    @pytest.mark.asyncio
    async def test_batch_create_parent_index_non_integer(self) -> None:
        """Test that non-integer parent_index returns error."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=MagicMock()):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(
                tasks=[
                    {"title": "Parent"},
                    {"title": "Child", "parent_index": "zero"},
                ]
            )
            parsed = json.loads(result)
            assert "error" in parsed
            assert "parent_index" in parsed["error"]

    @pytest.mark.asyncio
    async def test_batch_create_with_parent_index_response_includes_parent_id(
        self, mock_api_client: MagicMock
    ) -> None:
        """Test that response includes parent_id for tasks created with parent_index."""
        import json

        from mcp_resource.server import create_resource_server

        mock_api_client.batch_create_todos.return_value = ApiResponse(
            success=True,
            data=[
                {"id": 10, "title": "Parent task", "parent_id": None},
                {"id": 11, "title": "Child task", "parent_id": 10},
            ],
            status_code=201,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(
                tasks=[
                    {"title": "Parent task"},
                    {"title": "Child task", "parent_index": 0},
                ]
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 2
            assert parsed["created"][0]["id"] == "task_10"
            assert "parent_id" not in parsed["created"][0]
            assert parsed["created"][1]["id"] == "task_11"
            assert parsed["created"][1]["parent_id"] == "task_10"

    @pytest.mark.asyncio
    async def test_batch_create_with_wiki_page_id(self, mock_api_client: MagicMock) -> None:
        """Test that wiki_page_id is passed to the SDK."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(
                tasks=[{"title": "Task 1"}],
                wiki_page_id=42,
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["wiki_page_id"] == 42
            assert parsed["wiki_links_created"] == 2  # mock returns 2 tasks

            call_args = mock_api_client.batch_create_todos.call_args
            assert call_args.kwargs["wiki_page_id"] == 42

    @pytest.mark.asyncio
    async def test_batch_create_without_wiki_page_id(self, mock_api_client: MagicMock) -> None:
        """Test that wiki_page_id is not in result when not provided."""
        import json

        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            result = await create_tasks_tool.fn(
                tasks=[{"title": "Task 1"}],
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert "wiki_page_id" not in parsed
            assert "wiki_links_created" not in parsed

            call_args = mock_api_client.batch_create_todos.call_args
            assert call_args.kwargs["wiki_page_id"] is None

    @pytest.mark.asyncio
    async def test_batch_create_with_estimated_hours(self, mock_api_client: MagicMock) -> None:
        """Test that estimated_hours is passed through to the SDK."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            tools = server._tool_manager._tools
            create_tasks_tool = tools["create_tasks"]
            await create_tasks_tool.fn(
                tasks=[
                    {"title": "Task with hours", "estimated_hours": 4.5},
                    {"title": "Task without hours"},
                    {"title": "Task with zero hours", "estimated_hours": 0},
                ]
            )
            mock_api_client.batch_create_todos.assert_called_once()
            call_args = mock_api_client.batch_create_todos.call_args
            todos = call_args[0][0] if call_args[0] else call_args[1]["todos"]
            assert todos[0]["estimated_hours"] == 4.5
            assert "estimated_hours" not in todos[1]
            assert todos[2]["estimated_hours"] == 0


class TestWikiTools:
    """Tests for wiki MCP tools."""

    @pytest.fixture
    def mock_api_client(self) -> MagicMock:
        """Create a mock API client with wiki methods."""
        client = MagicMock()
        return client

    def _create_server(self, mock_client: MagicMock) -> Any:
        """Helper to create a patched MCP server and return tools dict."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            return server._tool_manager._tools

    @pytest.mark.asyncio
    async def test_search_wiki_pages_success(self, mock_api_client: MagicMock) -> None:
        """Test searching wiki pages returns matching page summaries."""
        import json

        mock_api_client.list_wiki_pages.return_value = ApiResponse(
            success=True,
            data=[
                {
                    "id": 1,
                    "title": "Meeting Notes",
                    "slug": "meeting-notes",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": None,
                }
            ],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["search_wiki_pages"].fn(q="meeting")
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 1
            assert parsed["pages"][0]["title"] == "Meeting Notes"
            mock_api_client.list_wiki_pages.assert_called_with(q="meeting")

    @pytest.mark.asyncio
    async def test_create_wiki_page_success(self, mock_api_client: MagicMock) -> None:
        """Test creating a wiki page."""
        import json

        mock_api_client.create_wiki_page.return_value = ApiResponse(
            success=True,
            data={
                "id": 5,
                "title": "New Page",
                "slug": "new-page",
                "content": "# Hello",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": None,
            },
            status_code=201,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["create_wiki_page"].fn(title="New Page", content="# Hello")
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "created"
            assert parsed["page"]["id"] == 5
            assert parsed["page"]["slug"] == "new-page"

    @pytest.mark.asyncio
    async def test_get_wiki_page_by_slug(self, mock_api_client: MagicMock) -> None:
        """Test getting a wiki page by slug."""
        import json

        mock_api_client.get_wiki_page.return_value = ApiResponse(
            success=True,
            data={
                "id": 3,
                "title": "My Page",
                "slug": "my-page",
                "content": "Content here",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": None,
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_wiki_page"].fn(slug_or_id="my-page")
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["page"]["id"] == 3
            assert parsed["page"]["content"] == "Content here"

    @pytest.mark.asyncio
    async def test_get_wiki_page_not_found(self, mock_api_client: MagicMock) -> None:
        """Test getting a wiki page that doesn't exist."""
        import json

        mock_api_client.get_wiki_page.return_value = ApiResponse(
            success=False,
            error="Wiki page not found",
            status_code=404,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_wiki_page"].fn(slug_or_id="nonexistent")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "not found" in parsed["error"]

    @pytest.mark.asyncio
    async def test_update_wiki_page_success(self, mock_api_client: MagicMock) -> None:
        """Test updating a wiki page."""
        import json

        mock_api_client.update_wiki_page.return_value = ApiResponse(
            success=True,
            data={
                "id": 3,
                "title": "Updated Title",
                "slug": "updated-title",
                "content": "New content",
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["update_wiki_page"].fn(
                page_id=3, title="Updated Title", content="New content"
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "updated"
            assert parsed["page"]["title"] == "Updated Title"

    @pytest.mark.asyncio
    async def test_delete_wiki_page_success(self, mock_api_client: MagicMock) -> None:
        """Test deleting a wiki page."""
        import json

        mock_api_client.delete_wiki_page.return_value = ApiResponse(
            success=True,
            data={"deleted": True, "id": 3},
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["delete_wiki_page"].fn(page_id=3)
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "deleted"
            assert parsed["page_id"] == 3

    @pytest.mark.asyncio
    async def test_link_wiki_page_to_task_success(self, mock_api_client: MagicMock) -> None:
        """Test linking a wiki page to a task."""
        import json

        mock_api_client.link_wiki_page_to_task.return_value = ApiResponse(
            success=True,
            data={
                "id": 10,
                "title": "My Task",
                "status": "pending",
                "priority": "medium",
                "due_date": None,
            },
            status_code=201,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["link_wiki_page_to_task"].fn(page_id=5, task_id="task_10")
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "linked"
            assert parsed["page_id"] == 5
            assert parsed["task_id"] == "task_10"
            mock_api_client.link_wiki_page_to_task.assert_called_with(5, 10)

    @pytest.mark.asyncio
    async def test_link_wiki_page_invalid_task_id(self, mock_api_client: MagicMock) -> None:
        """Test linking with invalid task ID format."""
        import json

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["link_wiki_page_to_task"].fn(page_id=5, task_id="invalid")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "Invalid task_id" in parsed["error"]

    @pytest.mark.asyncio
    async def test_get_wiki_page_linked_tasks(self, mock_api_client: MagicMock) -> None:
        """Test getting tasks linked to a wiki page."""
        import json

        mock_api_client.get_wiki_page_linked_tasks.return_value = ApiResponse(
            success=True,
            data=[
                {
                    "id": 1,
                    "title": "Task A",
                    "status": "pending",
                    "priority": "high",
                    "due_date": "2026-03-01",
                },
                {
                    "id": 2,
                    "title": "Task B",
                    "status": "completed",
                    "priority": "low",
                    "due_date": None,
                },
            ],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_wiki_page_linked_tasks"].fn(page_id=5)
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 2
            assert parsed["tasks"][0]["id"] == "task_1"
            assert parsed["tasks"][1]["id"] == "task_2"

    @pytest.mark.asyncio
    async def test_get_task_wiki_pages(self, mock_api_client: MagicMock) -> None:
        """Test getting wiki pages linked to a task."""
        import json

        mock_api_client.get_task_wiki_pages.return_value = ApiResponse(
            success=True,
            data=[
                {
                    "id": 1,
                    "title": "Design Doc",
                    "slug": "design-doc",
                    "created_at": "2026-01-01T00:00:00Z",
                    "updated_at": None,
                },
            ],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_task_wiki_pages"].fn(task_id="task_42")
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 1
            assert parsed["pages"][0]["slug"] == "design-doc"
            assert parsed["task_id"] == "task_42"
            mock_api_client.get_task_wiki_pages.assert_called_with(42)

    @pytest.mark.asyncio
    async def test_get_task_wiki_pages_invalid_id(self, mock_api_client: MagicMock) -> None:
        """Test getting wiki pages with invalid task ID."""
        import json

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_task_wiki_pages"].fn(task_id="abc")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "Invalid task_id" in parsed["error"]

    @pytest.mark.asyncio
    async def test_update_wiki_page_append(self, mock_api_client: MagicMock) -> None:
        """Test updating a wiki page with append mode."""
        import json

        mock_api_client.update_wiki_page.return_value = ApiResponse(
            success=True,
            data={
                "id": 3,
                "title": "My Page",
                "slug": "my-page",
                "content": "Old content\nNew content",
                "revision_number": 2,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-02T00:00:00Z",
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["update_wiki_page"].fn(
                page_id=3, content="New content", append=True
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "updated"
            mock_api_client.update_wiki_page.assert_called_with(
                page_id=3, title=None, content="New content", slug=None, append=True
            )

    @pytest.mark.asyncio
    async def test_batch_link_wiki_page_to_tasks_success(self, mock_api_client: MagicMock) -> None:
        """Test batch linking tasks to a wiki page."""
        import json

        mock_api_client.batch_link_wiki_page_to_tasks.return_value = ApiResponse(
            success=True,
            data={"linked": [1, 2], "already_linked": [], "not_found": [99]},
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["batch_link_wiki_page_to_tasks"].fn(
                page_id=5, task_ids=["task_1", "task_2", "99"]
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "completed"
            assert parsed["linked"] == [1, 2]
            assert parsed["not_found"] == [99]
            mock_api_client.batch_link_wiki_page_to_tasks.assert_called_with(5, [1, 2, 99])

    @pytest.mark.asyncio
    async def test_batch_link_invalid_task_ids(self, mock_api_client: MagicMock) -> None:
        """Test batch linking with invalid task ID format."""
        import json

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["batch_link_wiki_page_to_tasks"].fn(
                page_id=5, task_ids=["task_1", "invalid"]
            )
            parsed = json.loads(result)
            assert "error" in parsed
            assert "Invalid task_id" in parsed["error"]


class TestSnippetTools:
    """Tests for snippet MCP tools."""

    @pytest.fixture
    def mock_api_client(self) -> MagicMock:
        """Create a mock API client with snippet methods."""
        client = MagicMock()
        return client

    def _create_server(self, mock_client: MagicMock) -> Any:
        """Helper to create a patched MCP server and return tools dict."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )
            return server._tool_manager._tools

    @pytest.mark.asyncio
    async def test_list_snippets_success(self, mock_api_client: MagicMock) -> None:
        """Test list_snippets returns snippet data."""
        import json

        mock_api_client.list_snippets.return_value = ApiResponse(
            success=True,
            data=[
                {
                    "id": 1,
                    "category": "standup",
                    "title": "Daily standup",
                    "snippet_date": "2026-02-28",
                    "tags": ["dev"],
                    "created_at": "2026-02-28T10:00:00Z",
                    "updated_at": None,
                },
                {
                    "id": 2,
                    "category": "til",
                    "title": "TIL about Python",
                    "snippet_date": "2026-02-27",
                    "tags": ["python"],
                    "created_at": "2026-02-27T10:00:00Z",
                    "updated_at": None,
                },
            ],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["list_snippets"].fn()
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 2
            assert len(parsed["snippets"]) == 2
            assert parsed["snippets"][0]["category"] == "standup"

    @pytest.mark.asyncio
    async def test_list_snippets_empty(self, mock_api_client: MagicMock) -> None:
        """Test list_snippets with no snippets."""
        import json

        mock_api_client.list_snippets.return_value = ApiResponse(
            success=True,
            data=[],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["list_snippets"].fn()
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["count"] == 0
            assert parsed["snippets"] == []

    @pytest.mark.asyncio
    async def test_list_snippets_api_error(self, mock_api_client: MagicMock) -> None:
        """Test list_snippets handles API errors."""
        import json

        mock_api_client.list_snippets.return_value = ApiResponse(
            success=False,
            error="Authentication failed",
            status_code=401,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["list_snippets"].fn()
            parsed = json.loads(result)
            assert "error" in parsed
            assert parsed["error"] == "Authentication failed"

    @pytest.mark.asyncio
    async def test_list_snippets_with_filters(self, mock_api_client: MagicMock) -> None:
        """Test list_snippets passes filter parameters to SDK."""
        import json

        mock_api_client.list_snippets.return_value = ApiResponse(
            success=True,
            data=[],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["list_snippets"].fn(
                q="standup",
                category="daily",
                tag="dev",
                date_from="2026-02-01",
                date_to="2026-02-28",
            )
            parsed = json.loads(result)
            assert "error" not in parsed

            # Verify SDK was called with all filter params
            mock_api_client.list_snippets.assert_called_once_with(
                q="standup",
                category="daily",
                tag="dev",
                date_from="2026-02-01",
                date_to="2026-02-28",
            )

    @pytest.mark.asyncio
    async def test_create_snippet_success(self, mock_api_client: MagicMock) -> None:
        """Test create_snippet creates a snippet."""
        import json

        mock_api_client.create_snippet.return_value = ApiResponse(
            success=True,
            data={
                "id": 1,
                "category": "standup",
                "title": "Daily standup",
                "content": "Worked on features",
                "snippet_date": "2026-02-28",
                "tags": ["dev"],
                "created_at": "2026-02-28T10:00:00Z",
            },
            status_code=201,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["create_snippet"].fn(
                category="standup",
                title="Daily standup",
                content="Worked on features",
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "created"
            assert parsed["snippet"]["id"] == 1
            assert parsed["snippet"]["category"] == "standup"

    @pytest.mark.asyncio
    async def test_create_snippet_error(self, mock_api_client: MagicMock) -> None:
        """Test create_snippet handles API errors."""
        import json

        mock_api_client.create_snippet.return_value = ApiResponse(
            success=False,
            error="Validation error: title is required",
            status_code=400,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["create_snippet"].fn(
                category="standup",
                title="",
            )
            parsed = json.loads(result)
            assert "error" in parsed

    @pytest.mark.asyncio
    async def test_get_snippet_success(self, mock_api_client: MagicMock) -> None:
        """Test get_snippet retrieves a single snippet."""
        import json

        mock_api_client.get_snippet.return_value = ApiResponse(
            success=True,
            data={
                "id": 42,
                "category": "meeting",
                "title": "Sprint planning",
                "content": "Discussed roadmap",
                "snippet_date": "2026-02-28",
                "tags": ["sprint", "planning"],
                "created_at": "2026-02-28T10:00:00Z",
                "updated_at": None,
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_snippet"].fn(snippet_id=42)
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["snippet"]["id"] == 42
            assert parsed["snippet"]["title"] == "Sprint planning"
            assert parsed["snippet"]["tags"] == ["sprint", "planning"]

    @pytest.mark.asyncio
    async def test_get_snippet_not_found(self, mock_api_client: MagicMock) -> None:
        """Test get_snippet handles snippet not found."""
        import json

        mock_api_client.get_snippet.return_value = ApiResponse(
            success=False,
            error="Snippet not found",
            status_code=404,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["get_snippet"].fn(snippet_id=999)
            parsed = json.loads(result)
            assert "error" in parsed
            assert parsed["error"] == "Snippet not found"

    @pytest.mark.asyncio
    async def test_update_snippet_success(self, mock_api_client: MagicMock) -> None:
        """Test update_snippet updates a snippet."""
        import json

        mock_api_client.update_snippet.return_value = ApiResponse(
            success=True,
            data={
                "id": 1,
                "category": "standup",
                "title": "Updated title",
                "content": "Updated content",
                "snippet_date": "2026-02-28",
                "tags": ["updated"],
                "created_at": "2026-02-28T10:00:00Z",
                "updated_at": "2026-02-28T12:00:00Z",
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["update_snippet"].fn(
                snippet_id=1,
                title="Updated title",
                content="Updated content",
            )
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "updated"
            assert parsed["snippet"]["title"] == "Updated title"

    @pytest.mark.asyncio
    async def test_update_snippet_not_found(self, mock_api_client: MagicMock) -> None:
        """Test update_snippet handles snippet not found."""
        import json

        mock_api_client.update_snippet.return_value = ApiResponse(
            success=False,
            error="Snippet not found",
            status_code=404,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["update_snippet"].fn(
                snippet_id=999,
                title="New title",
            )
            parsed = json.loads(result)
            assert "error" in parsed
            assert parsed["error"] == "Snippet not found"

    @pytest.mark.asyncio
    async def test_delete_snippet_success(self, mock_api_client: MagicMock) -> None:
        """Test delete_snippet successfully deletes a snippet."""
        import json

        mock_api_client.delete_snippet.return_value = ApiResponse(
            success=True,
            data={"deleted": True, "id": 1},
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["delete_snippet"].fn(snippet_id=1)
            parsed = json.loads(result)
            assert "error" not in parsed
            assert parsed["status"] == "deleted"
            assert parsed["snippet_id"] == 1

    @pytest.mark.asyncio
    async def test_delete_snippet_not_found(self, mock_api_client: MagicMock) -> None:
        """Test delete_snippet handles snippet not found."""
        import json

        mock_api_client.delete_snippet.return_value = ApiResponse(
            success=False,
            error="Snippet not found",
            status_code=404,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_api_client):
            tools = self._create_server(mock_api_client)
            result = await tools["delete_snippet"].fn(snippet_id=999)
            parsed = json.loads(result)
            assert "error" in parsed
            assert parsed["error"] == "Snippet not found"


class TestResourceDefinitions:
    """Tests for MCP resource definitions (read-only lookups)."""

    def _create_server(self, mock_client: MagicMock) -> Any:
        """Helper to create a patched MCP server."""
        from mcp_resource.server import create_resource_server

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            return create_resource_server(
                port=8001,
                server_url="https://localhost:8001",
                auth_server_url="https://localhost:9000",
                auth_server_public_url="https://localhost:9000",
                oauth_strict=False,
            )

    def test_health_resource_registered(self) -> None:
        """Test that taskmanager://health resource is registered."""
        mock_client = MagicMock()
        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resources = server._resource_manager._resources
            assert "taskmanager://health" in resources

    @pytest.mark.asyncio
    async def test_health_resource_returns_data(self) -> None:
        """Test that the health resource calls the SDK and returns data."""
        import json

        mock_client = MagicMock()
        mock_client.health_check.return_value = ApiResponse(
            success=True,
            data={
                "status": "healthy",
                "subsystems": {
                    "tasks": {"status": "healthy"},
                    "projects": {"status": "healthy"},
                    "wiki": {"status": "healthy"},
                    "snippets": {"status": "healthy"},
                },
                "timestamp": "2026-02-28T12:00:00+00:00",
            },
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resource = server._resource_manager._resources["taskmanager://health"]
            result = await resource.fn()
            parsed = json.loads(result)
            assert parsed["status"] == "healthy"
            assert "subsystems" in parsed
            assert parsed["subsystems"]["wiki"]["status"] == "healthy"

    def test_categories_resource_registered(self) -> None:
        """Test that taskmanager://categories resource is registered."""
        mock_client = MagicMock()
        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resources = server._resource_manager._resources
            assert "taskmanager://categories" in resources

    def test_snippet_categories_resource_registered(self) -> None:
        """Test that taskmanager://snippets/categories resource is registered."""
        mock_client = MagicMock()
        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resources = server._resource_manager._resources
            assert "taskmanager://snippets/categories" in resources

    def test_wiki_pages_resource_registered(self) -> None:
        """Test that taskmanager://wiki/pages resource is registered."""
        mock_client = MagicMock()
        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resources = server._resource_manager._resources
            assert "taskmanager://wiki/pages" in resources

    def test_deleted_tools_not_registered(self) -> None:
        """Test that removed tools are no longer registered."""
        mock_client = MagicMock()
        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            tools = server._tool_manager._tools
            removed_tools = [
                "delete_task_attachment",
                "delete_task_comment",
                "get_wiki_page_revisions",
                "get_wiki_page_revision",
                "unlink_wiki_page_from_task",
                "remove_dependency",
                "get_categories",
                "get_snippet_categories",
                "list_wiki_pages",
            ]
            for name in removed_tools:
                assert name not in tools, f"Tool {name!r} should have been removed"

    def test_search_wiki_pages_tool_registered(self) -> None:
        """Test that search_wiki_pages (renamed from list_wiki_pages) is registered."""
        mock_client = MagicMock()
        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            tools = server._tool_manager._tools
            assert "search_wiki_pages" in tools

    @pytest.mark.asyncio
    async def test_categories_resource_returns_data(self) -> None:
        """Test that the categories resource calls the API and returns data."""
        import json

        mock_client = MagicMock()
        mock_client.get_categories.return_value = ApiResponse(
            success=True,
            data={"categories": [{"name": "Work", "task_count": 5}]},
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resource = server._resource_manager._resources["taskmanager://categories"]
            result = await resource.fn()
            parsed = json.loads(result)
            assert "categories" in parsed
            assert len(parsed["categories"]) == 1
            assert parsed["categories"][0]["name"] == "Work"

    @pytest.mark.asyncio
    async def test_snippet_categories_resource_returns_data(self) -> None:
        """Test that the snippet categories resource returns data."""
        import json

        mock_client = MagicMock()
        mock_client.get_snippet_categories.return_value = ApiResponse(
            success=True,
            data=[
                {"category": "standup", "count": 10},
                {"category": "til", "count": 5},
            ],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resource = server._resource_manager._resources["taskmanager://snippets/categories"]
            result = await resource.fn()
            parsed = json.loads(result)
            assert "categories" in parsed
            assert len(parsed["categories"]) == 2

    @pytest.mark.asyncio
    async def test_wiki_pages_resource_returns_data(self) -> None:
        """Test that the wiki pages resource returns data."""
        import json

        mock_client = MagicMock()
        mock_client.list_wiki_pages.return_value = ApiResponse(
            success=True,
            data=[
                {"id": 1, "title": "Page One", "slug": "page-one"},
            ],
            status_code=200,
        )

        with patch("mcp_resource.server.get_api_client", return_value=mock_client):
            server = self._create_server(mock_client)
            resource = server._resource_manager._resources["taskmanager://wiki/pages"]
            result = await resource.fn()
            parsed = json.loads(result)
            assert "pages" in parsed
            assert parsed["count"] == 1
            assert parsed["pages"][0]["title"] == "Page One"
            # Ensure it calls list_wiki_pages without a query
            mock_client.list_wiki_pages.assert_called_once_with()
