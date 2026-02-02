"""Todo API routes."""

from datetime import UTC, date, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, select

from app.core.errors import errors
from app.db.queries import (
    get_next_position,
    get_resource_for_user,
    get_resources_for_user,
)
from app.dependencies import CurrentUser, DbSession
from app.models.project import Project
from app.models.todo import ActionType, AgentStatus, Priority, Status, Todo
from app.schemas import ListResponse

router = APIRouter(prefix="/api/todos", tags=["todos"])


# Schemas
class TodoCreate(BaseModel):
    """Create todo request."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: Priority = Priority.medium
    status: Status = Status.pending
    due_date: date | None = None
    project_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    context: str | None = None
    estimated_hours: float | None = None
    parent_id: int | None = None
    position: int | None = None
    # Agent fields - typically not set on creation, inferred automatically
    agent_actionable: bool | None = None
    action_type: ActionType | None = None


class TodoUpdate(BaseModel):
    """Update todo request."""

    title: str | None = None
    description: str | None = None
    priority: Priority | None = None
    status: Status | None = None
    due_date: date | None = None
    project_id: int | None = None
    tags: list[str] | None = None
    context: str | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None
    parent_id: int | None = None
    position: int | None = None
    # Agent fields
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    agent_status: AgentStatus | None = None
    agent_notes: str | None = None
    blocking_reason: str | None = None


class BulkUpdateRequest(BaseModel):
    """Bulk update request."""

    ids: list[int]
    updates: TodoUpdate


class SubtaskResponse(BaseModel):
    """Subtask response (simplified todo for nested display)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    priority: Priority
    status: Status
    due_date: date | None
    estimated_hours: float | None
    actual_hours: float | None
    position: int
    created_at: datetime
    updated_at: datetime | None
    # Agent fields
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    agent_status: AgentStatus | None = None


class TodoResponse(BaseModel):
    """Todo response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    priority: Priority
    status: Status
    due_date: date | None
    project_id: int | None
    project_name: str | None = None
    project_color: str | None = None
    tags: list[str]
    context: str | None
    estimated_hours: float | None
    actual_hours: float | None
    position: int
    parent_id: int | None = None
    subtasks: list[SubtaskResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None
    # Agent fields
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    agent_status: AgentStatus | None = None
    agent_notes: str | None = None
    blocking_reason: str | None = None


# Helper functions
def _build_subtask_response(subtask: Todo) -> SubtaskResponse:
    """Build SubtaskResponse from Todo model.

    Args:
        subtask: Todo model instance (child task)

    Returns:
        SubtaskResponse with all fields populated
    """
    return SubtaskResponse(
        id=subtask.id,
        title=subtask.title,
        description=subtask.description,
        priority=subtask.priority,
        status=subtask.status,
        due_date=subtask.due_date,
        estimated_hours=float(subtask.estimated_hours)
        if subtask.estimated_hours
        else None,
        actual_hours=float(subtask.actual_hours) if subtask.actual_hours else None,
        position=subtask.position,
        created_at=subtask.created_at,
        updated_at=subtask.updated_at,
        agent_actionable=subtask.agent_actionable,
        action_type=subtask.action_type,
        agent_status=subtask.agent_status,
    )


def _build_todo_response(
    todo: Todo,
    project_name: str | None = None,
    project_color: str | None = None,
    subtasks: list[Todo] | None = None,
) -> TodoResponse:
    """Build TodoResponse from Todo model with optional project info.

    Args:
        todo: Todo model instance
        project_name: Optional project name
        project_color: Optional project color
        subtasks: Optional list of subtask Todo instances

    Returns:
        TodoResponse with all fields populated
    """
    subtask_responses = []
    if subtasks:
        subtask_responses = [
            _build_subtask_response(s) for s in subtasks if s.deleted_at is None
        ]

    return TodoResponse(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        priority=todo.priority,
        status=todo.status,
        due_date=todo.due_date,
        project_id=todo.project_id,
        project_name=project_name,
        project_color=project_color,
        tags=todo.tags or [],
        context=todo.context,
        estimated_hours=float(todo.estimated_hours) if todo.estimated_hours else None,
        actual_hours=float(todo.actual_hours) if todo.actual_hours else None,
        position=todo.position,
        parent_id=todo.parent_id,
        subtasks=subtask_responses,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
        agent_actionable=todo.agent_actionable,
        action_type=todo.action_type,
        agent_status=todo.agent_status,
        agent_notes=todo.agent_notes,
        blocking_reason=todo.blocking_reason,
    )


# Rule-based action type inference patterns
# Each entry: action_type -> (keywords, agent_actionable)
ACTION_PATTERNS: dict[ActionType, tuple[list[str], bool]] = {
    ActionType.research: (
        [
            "research",
            "find out",
            "look up",
            "investigate",
            "learn about",
            "explore",
            "discover",
            "analyze",
            "study",
            "review options",
            "compare",
        ],
        True,  # Agent can do research
    ),
    ActionType.code: (
        [
            "implement",
            "fix bug",
            "refactor",
            "write code",
            "build",
            "debug",
            "code",
            "program",
            "develop",
            "create script",
            "automate",
        ],
        True,  # Agent can write/modify code
    ),
    ActionType.email: (
        [
            "email",
            "send",
            "reply",
            "follow up with",
            "draft",
            "respond to",
            "write to",
            "contact via email",
            "compose",
        ],
        True,  # Agent can draft emails
    ),
    ActionType.document: (
        [
            "write",
            "document",
            "create doc",
            "draft document",
            "prepare report",
            "write up",
            "summarize",
            "create summary",
        ],
        True,  # Agent can create documents
    ),
    ActionType.review: (
        ["review", "check", "proofread", "audit", "evaluate", "assess", "inspect"],
        True,  # Agent can review content
    ),
    ActionType.data_entry: (
        ["enter data", "input", "fill out", "update spreadsheet", "log", "record"],
        True,  # Agent can do data entry with proper access
    ),
    ActionType.purchase: (
        ["buy", "purchase", "order", "book", "reserve", "subscribe"],
        False,  # Needs human approval/payment
    ),
    ActionType.schedule: (
        [
            "schedule",
            "set up meeting",
            "arrange",
            "plan meeting",
            "book time",
            "calendar",
            "set appointment",
        ],
        False,  # Needs human for scheduling decisions
    ),
    ActionType.call: (
        ["call", "phone", "dial", "ring", "speak with", "talk to"],
        False,  # Agent can't make phone calls
    ),
    ActionType.errand: (
        ["pick up", "drop off", "go to", "visit", "attend", "deliver", "collect"],
        False,  # Physical presence required
    ),
    ActionType.manual: (
        [
            "physically",
            "in person",
            "hands-on",
            "manually",
            "assemble",
            "install",
            "repair",
            "fix physically",
            "clean",
            "organize physically",
        ],
        False,  # Physical action required
    ),
}


def infer_action_type(
    title: str, description: str | None
) -> tuple[ActionType | None, bool | None]:
    """Infer action type and agent actionability from task title/description.

    Uses keyword matching to classify tasks. Returns (None, None) if no
    pattern matches, allowing the agent to classify later via LLM.

    Args:
        title: Task title
        description: Optional task description

    Returns:
        Tuple of (action_type, agent_actionable) or (None, None) if unknown
    """
    text = f"{title} {description or ''}".lower()

    for action_type, (keywords, actionable) in ACTION_PATTERNS.items():
        if any(keyword in text for keyword in keywords):
            return action_type, actionable

    return None, None  # Unknown - agent can classify later


@router.get("")
async def list_todos(
    user: CurrentUser,
    db: DbSession,
    status: str | None = Query(None),
    project_id: int | None = Query(None),
    category: str | None = Query(None),
    start_date: date | None = Query(None),  # noqa: B008
    end_date: date | None = Query(None),  # noqa: B008
    parent_id: int | None = Query(None),
    include_subtasks: bool = Query(False),
    order_by: str | None = Query(None, description="Order by: position or due_date"),
) -> ListResponse[TodoResponse]:
    """List todos with optional filters.

    By default, only returns root-level todos (no parent).
    Use parent_id to get subtasks of a specific todo.
    Use include_subtasks=true to include subtasks in the response.
    Use order_by='position' to sort by manual position instead of due date.
    """
    query = (
        select(
            Todo,
            Project.name.label("project_name"),
            Project.color.label("project_color"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(Todo.user_id == user.id)
        .where(Todo.deleted_at.is_(None))
    )

    # Filter by parent_id - if not specified, only show root-level todos
    if parent_id is not None:
        query = query.where(Todo.parent_id == parent_id)
    else:
        query = query.where(Todo.parent_id.is_(None))

    # Apply filters
    if status and status != "all":
        if status == "overdue":
            query = query.where(
                and_(
                    Todo.due_date < date.today(),
                    Todo.status != Status.completed,
                )
            )
        else:
            query = query.where(Todo.status == status)

    if project_id:
        query = query.where(Todo.project_id == project_id)

    if category:
        query = query.join(Project).where(Project.name == category)

    if start_date:
        query = query.where(Todo.due_date >= start_date)

    if end_date:
        query = query.where(Todo.due_date <= end_date)

    # Apply ordering
    if order_by == "position":
        query = query.order_by(Todo.position, Todo.created_at)
    else:
        query = query.order_by(Todo.due_date.asc().nulls_last(), Todo.priority.desc())

    result = await db.execute(query)
    rows = result.all()

    # Fetch subtasks for each todo if requested
    subtasks_map: dict[int, list[Todo]] = {}
    if include_subtasks:
        todo_ids = [row[0].id for row in rows]
        if todo_ids:
            subtasks_query = (
                select(Todo)
                .where(Todo.parent_id.in_(todo_ids))
                .where(Todo.deleted_at.is_(None))
                .order_by(Todo.position, Todo.created_at.asc())
            )
            subtasks_result = await db.execute(subtasks_query)
            for subtask in subtasks_result.scalars().all():
                parent_id = subtask.parent_id
                if parent_id is not None:
                    if parent_id not in subtasks_map:
                        subtasks_map[parent_id] = []
                    subtasks_map[parent_id].append(subtask)

    tasks = []
    for row in rows:
        todo = row[0]
        subtasks = subtasks_map.get(todo.id, []) if include_subtasks else []
        tasks.append(
            _build_todo_response(
                todo,
                project_name=row.project_name,
                project_color=row.project_color,
                subtasks=subtasks,
            )
        )

    return ListResponse(data=tasks, meta={"count": len(tasks)})


@router.post("", status_code=201)
async def create_todo(
    request: TodoCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a new todo or subtask.

    To create a subtask, provide the parent_id of the parent todo.
    """
    # Verify parent todo exists and belongs to user if parent_id is provided
    if request.parent_id:
        await get_resource_for_user(
            db, Todo, request.parent_id, user.id, errors.todo_not_found
        )

    # Auto-assign position if not provided
    position = request.position
    if position is None:
        position = await get_next_position(
            db, Todo, user.id, parent_id=request.parent_id
        )

    # Infer agent fields if not provided
    agent_actionable = request.agent_actionable
    action_type = request.action_type
    if agent_actionable is None or action_type is None:
        inferred_type, inferred_actionable = infer_action_type(
            request.title, request.description
        )
        if action_type is None:
            action_type = inferred_type
        if agent_actionable is None:
            agent_actionable = inferred_actionable

    todo = Todo(
        user_id=user.id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        status=request.status,
        due_date=request.due_date,
        project_id=request.project_id,
        tags=request.tags,
        context=request.context,
        estimated_hours=request.estimated_hours,
        parent_id=request.parent_id,
        position=position,
        agent_actionable=agent_actionable,
        action_type=action_type,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)

    # Fetch project info if todo has a project
    project_name = None
    project_color = None
    if todo.project_id:
        project_result = await db.execute(
            select(Project).where(
                Project.id == todo.project_id, Project.user_id == user.id
            )
        )
        project = project_result.scalar_one_or_none()
        if project:
            project_name = project.name
            project_color = project.color

    return {"data": _build_todo_response(todo, project_name, project_color)}


@router.get("/{todo_id}")
async def get_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Get a todo by ID with its subtasks."""
    # Verify todo exists and belongs to user, get with project info
    result = await db.execute(
        select(
            Todo,
            Project.name.label("project_name"),
            Project.color.label("project_color"),
        )
        .outerjoin(Project, Todo.project_id == Project.id)
        .where(Todo.id == todo_id, Todo.user_id == user.id)
    )
    row = result.one_or_none()

    if not row:
        raise errors.todo_not_found()

    todo = row[0]

    # Fetch subtasks
    subtasks_result = await db.execute(
        select(Todo)
        .where(Todo.parent_id == todo_id, Todo.deleted_at.is_(None))
        .order_by(Todo.created_at.asc())
    )
    subtasks = list(subtasks_result.scalars().all())

    return {
        "data": _build_todo_response(
            todo,
            project_name=row.project_name,
            project_color=row.project_color,
            subtasks=subtasks,
        )
    }


@router.put("/{todo_id}")
async def update_todo(
    todo_id: int,
    request: TodoUpdate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Update a todo."""
    todo = await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found, check_deleted=False
    )

    # Verify parent_id authorization if being updated
    update_data = request.model_dump(exclude_unset=True)
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        parent = await get_resource_for_user(
            db, Todo, update_data["parent_id"], user.id, errors.todo_not_found
        )

        # Prevent nested subtasks (subtasks of subtasks)
        if parent.parent_id is not None:
            raise errors.validation(
                "Cannot create subtasks of subtasks. "
                "Only one level of nesting is allowed."
            )

    # Update fields
    for field, value in update_data.items():
        setattr(todo, field, value)

    # Commit the changes
    await db.commit()
    await db.refresh(todo)

    # Fetch project info if todo has a project
    project_name = None
    project_color = None
    if todo.project_id:
        project_result = await db.execute(
            select(Project).where(
                Project.id == todo.project_id,
                Project.user_id
                == user.id,  # Authorization check: verify project belongs to user
            )
        )
        project = project_result.scalar_one_or_none()
        if project:
            project_name = project.name
            project_color = project.color

    # Return full todo object
    return {"data": _build_todo_response(todo, project_name, project_color)}


@router.put("")
async def bulk_update_todos(
    request: BulkUpdateRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Bulk update todos."""
    todos_dict = await get_resources_for_user(db, Todo, request.ids, user.id)
    todos = list(todos_dict.values())

    # Verify parent_id authorization if being updated
    update_data = request.updates.model_dump(exclude_unset=True)
    if "parent_id" in update_data and update_data["parent_id"] is not None:
        parent = await get_resource_for_user(
            db, Todo, update_data["parent_id"], user.id, errors.todo_not_found
        )

        # Prevent nested subtasks (subtasks of subtasks)
        if parent.parent_id is not None:
            raise errors.validation(
                "Cannot create subtasks of subtasks. "
                "Only one level of nesting is allowed."
            )

    for todo in todos:
        for field, value in update_data.items():
            setattr(todo, field, value)

    return {"data": {"updated": len(todos)}}


@router.delete("/{todo_id}")
async def delete_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Soft delete a todo."""
    todo = await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found, check_deleted=False
    )

    todo.deleted_at = datetime.now(UTC)

    return {"data": {"deleted": True}}


@router.post("/{todo_id}/complete")
async def complete_todo(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Mark a todo as complete."""
    todo = await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found, check_deleted=False
    )

    todo.status = Status.completed
    todo.completed_date = datetime.now(UTC)

    return {"data": {"completed": True}}


# Subtask endpoints
class SubtaskCreate(BaseModel):
    """Create subtask request (simplified todo creation)."""

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: Priority = Priority.medium
    due_date: date | None = None
    estimated_hours: float | None = None


@router.get("/{todo_id}/subtasks")
async def list_subtasks(
    todo_id: int,
    user: CurrentUser,
    db: DbSession,
) -> ListResponse[SubtaskResponse]:
    """List all subtasks for a todo."""
    # Verify parent todo exists and belongs to user
    await get_resource_for_user(db, Todo, todo_id, user.id, errors.todo_not_found)

    # Fetch subtasks
    result = await db.execute(
        select(Todo)
        .where(Todo.parent_id == todo_id, Todo.deleted_at.is_(None))
        .order_by(Todo.position, Todo.created_at.asc())
    )
    subtasks = result.scalars().all()

    return ListResponse(
        data=[_build_subtask_response(s) for s in subtasks],
        meta={"count": len(subtasks)},
    )


@router.post("/{todo_id}/subtasks", status_code=201)
async def create_subtask(
    todo_id: int,
    request: SubtaskCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Create a subtask for a todo."""
    # Verify parent todo exists and belongs to user
    parent = await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found
    )

    # Prevent nested subtasks (subtasks of subtasks)
    if parent.parent_id is not None:
        raise errors.validation(
            "Cannot create subtasks of subtasks. Only one level of nesting is allowed."
        )

    # Auto-assign position for the subtask
    position = await get_next_position(db, Todo, user.id, parent_id=todo_id)

    subtask = Todo(
        user_id=user.id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        status=Status.pending,
        due_date=request.due_date,
        estimated_hours=request.estimated_hours,
        parent_id=todo_id,
        project_id=parent.project_id,  # Inherit project from parent
        tags=[],
        position=position,
    )
    db.add(subtask)
    await db.flush()
    await db.refresh(subtask)

    return {"data": _build_subtask_response(subtask)}


class TodoReorderRequest(BaseModel):
    """Reorder todos request."""

    todo_ids: list[int] = Field(..., min_length=1)


@router.post("/reorder")
async def reorder_todos(
    request: TodoReorderRequest,
    user: CurrentUser,
    db: DbSession,
) -> dict:
    """Reorder todos by providing the new order of todo IDs."""
    # Fetch all todos for user
    todos = await get_resources_for_user(db, Todo, request.todo_ids, user.id)

    # Validate all requested IDs were found and belong to user
    if len(todos) != len(request.todo_ids):
        missing_ids = set(request.todo_ids) - set(todos.keys())
        raise errors.not_found(f"Todos not found: {missing_ids}")

    # Update positions based on order in the list
    for position, todo_id in enumerate(request.todo_ids):
        todos[todo_id].position = position

    return {"data": {"reordered": len(todos)}}
