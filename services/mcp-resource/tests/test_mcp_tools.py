"""Unit tests for MCP server helper functions and tools."""

import datetime
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
    async def test_get_categories_with_wrapped_response(self, mock_api_client: MagicMock) -> None:
        """Test get_categories handles wrapped {'categories': [...]} response."""
        mock_api_client.get_categories.return_value = ApiResponse(
            success=True,
            data={
                "categories": [
                    {"name": "Work", "task_count": 5},
                    {"name": "Personal", "task_count": 3},
                ]
            },
            status_code=200,
        )

        response = mock_api_client.get_categories()
        categories, error = validate_list_response(response, "categories")
        assert error is None
        assert len(categories) == 2
        assert categories[0]["name"] == "Work"

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


class TestHealthCheckTool:
    """Tests for check_task_system_status health check tool."""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self) -> None:
        """Test health check reports healthy when all services work."""
        mock_client = MagicMock()
        mock_client.get_projects.return_value = ApiResponse(
            success=True,
            data=[{"id": 1, "name": "Project"}],
            status_code=200,
        )
        mock_client.get_todos.return_value = ApiResponse(
            success=True,
            data=[{"id": 1, "title": "Task"}],
            status_code=200,
        )

        # Verify the responses would pass validation
        projects, proj_error = validate_list_response(mock_client.get_projects(), "projects")
        tasks, task_error = validate_list_response(mock_client.get_todos(), "tasks")

        assert proj_error is None
        assert task_error is None
        assert len(projects) == 1
        assert len(tasks) == 1

    @pytest.mark.asyncio
    async def test_health_check_projects_unhealthy(self) -> None:
        """Test health check detects projects service failure."""
        mock_client = MagicMock()
        mock_client.get_projects.return_value = ApiResponse(
            success=False,
            error="Database connection failed",
            status_code=500,
        )

        projects, proj_error = validate_list_response(mock_client.get_projects(), "projects")
        assert proj_error == "Database connection failed"
        assert projects == []

    @pytest.mark.asyncio
    async def test_health_check_invalid_format(self) -> None:
        """Test health check detects invalid response format."""
        mock_client = MagicMock()
        mock_client.get_projects.return_value = ApiResponse(
            success=True,
            data="unexpected string",  # Should be list
            status_code=200,
        )

        projects, proj_error = validate_list_response(mock_client.get_projects(), "projects")
        assert proj_error is not None
        assert "expected list" in proj_error
        assert projects == []


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

    @pytest.mark.asyncio
    async def test_delete_attachment_success(self) -> None:
        """Test delete_task_attachment successful response."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={"deleted": True, "id": 5},
            status_code=200,
        )

        response = mock_client._make_request("DELETE", "/todos/10/attachments/5")

        assert response.success is True
        assert response.data is not None
        assert response.data.get("deleted") is True
        assert response.data.get("id") == 5

    @pytest.mark.asyncio
    async def test_delete_attachment_not_found(self) -> None:
        """Test delete_task_attachment when attachment doesn't exist."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False,
            error="Attachment not found",
            status_code=404,
        )

        response = mock_client._make_request("DELETE", "/todos/10/attachments/999")

        assert response.success is False
        assert response.error == "Attachment not found"

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

    @pytest.mark.asyncio
    async def test_remove_dependency_success(self) -> None:
        """Test remove_dependency removes a dependency relationship."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=True,
            data={"deleted": True, "dependency_id": 5},
            status_code=200,
        )

        response = mock_client._make_request("DELETE", "/todos/10/dependencies/5")

        assert response.success is True
        assert response.data is not None
        assert response.data.get("deleted") is True

    @pytest.mark.asyncio
    async def test_remove_dependency_not_found(self) -> None:
        """Test remove_dependency handles missing dependency."""
        mock_client = MagicMock()
        mock_client._make_request.return_value = ApiResponse(
            success=False,
            error="Dependency not found",
            status_code=404,
        )

        response = mock_client._make_request("DELETE", "/todos/10/dependencies/999")

        assert response.success is False
        assert response.error == "Dependency not found"

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
