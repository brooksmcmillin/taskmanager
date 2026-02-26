"""Todo API routes."""

from datetime import UTC, date, datetime
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, case, select

from app.core.errors import errors
from app.db.queries import (
    get_next_position,
    get_project_info,
    get_resource_for_user,
    get_resources_for_user,
)
from app.dependencies import CurrentUserFlexible, DbSession
from app.models.project import Project
from app.models.todo import (
    ACTION_TYPE_DEFAULT_TIER,
    ActionType,
    AgentStatus,
    DeadlineType,
    Priority,
    Status,
    Todo,
    task_dependencies,
)
from app.schemas import ListResponse

router = APIRouter(prefix="/api/todos", tags=["todos"])


# Schemas
class TodoCreate(BaseModel):
    """Create todo request."""

    model_config = ConfigDict(use_enum_values=True)

    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    priority: Priority = Priority.medium
    status: Status = Status.pending
    due_date: date | None = None
    deadline_type: DeadlineType = DeadlineType.preferred
    project_id: int | None = None
    category: str | None = Field(
        None, description="Project name (resolved to project_id)"
    )
    tags: list[str] = Field(default_factory=list)
    context: str | None = None
    estimated_hours: float | None = None
    parent_id: int | None = None
    parent_index: int | None = Field(
        None,
        description=(
            "0-based index of another task in the same batch to use as parent. "
            "Only valid in batch creation. Mutually exclusive with parent_id."
        ),
    )
    position: int | None = None
    # Agent fields - typically not set on creation, inferred automatically
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    autonomy_tier: int | None = Field(
        None, ge=1, le=4, description="Risk level: 1-4 (1=fully autonomous, 4=never)"
    )
    # Batch-only: 0-based indices of other tasks in the batch that this task depends on
    depends_on: list[int] | None = Field(
        None,
        description="List of 0-based indices of other tasks in the same batch "
        "that this task depends on. Only used in batch creation.",
    )


class TodoUpdate(BaseModel):
    """Update todo request."""

    model_config = ConfigDict(use_enum_values=True)

    title: str | None = None
    description: str | None = None
    priority: Priority | None = None
    status: Status | None = None
    due_date: date | None = None
    deadline_type: DeadlineType | None = None
    project_id: int | None = None
    category: str | None = Field(
        None, description="Project name (resolved to project_id)"
    )
    tags: list[str] | None = None
    context: str | None = None
    estimated_hours: float | None = None
    actual_hours: float | None = None
    parent_id: int | None = None
    position: int | None = None
    # Agent fields
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    autonomy_tier: int | None = Field(
        None, ge=1, le=4, description="Risk level: 1-4 (1=fully autonomous, 4=never)"
    )
    agent_status: AgentStatus | None = None
    agent_notes: str | None = None
    blocking_reason: str | None = None


class BatchTodoCreate(BaseModel):
    """Batch todo creation request.

    Supports inline parent-child relationships via ``parent_index``.  Each
    task may reference another task in the same batch by its 0-based index
    to declare it as its parent.  The referenced task must appear before
    the child (i.e. a task cannot reference a later index), must not be a
    subtask itself (only one level of nesting), and ``parent_index`` is
    mutually exclusive with ``parent_id``.
    """

    todos: list[TodoCreate] = Field(..., min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_parent_indexes(self) -> "BatchTodoCreate":
        """Validate all parent_index references in the batch."""
        for i, item in enumerate(self.todos):
            if item.parent_index is not None and item.parent_id is not None:
                raise ValueError(
                    f"Todo at index {i}: cannot specify both parent_id and parent_index"
                )

            if item.parent_index is not None:
                idx = item.parent_index
                if idx < 0 or idx >= len(self.todos):
                    raise ValueError(
                        f"Todo at index {i}: parent_index {idx} is out of "
                        f"range (batch has {len(self.todos)} items, "
                        f"valid range 0-{len(self.todos) - 1})"
                    )
                if idx == i:
                    raise ValueError(
                        f"Todo at index {i}: parent_index cannot reference itself"
                    )
                if idx > i:
                    raise ValueError(
                        f"Todo at index {i}: parent_index {idx} references a "
                        f"later item. Parents must appear before children in "
                        f"the batch."
                    )
                # Ensure parent is not itself a subtask (only 1 level)
                parent = self.todos[idx]
                if parent.parent_index is not None or parent.parent_id is not None:
                    raise ValueError(
                        f"Todo at index {i}: parent at index {idx} is itself "
                        f"a subtask. Only one level of nesting is allowed."
                    )
        return self


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
    deadline_type: DeadlineType = DeadlineType.preferred
    estimated_hours: float | None
    actual_hours: float | None
    position: int
    created_at: datetime
    updated_at: datetime | None
    # Agent fields
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    autonomy_tier: int | None = None
    agent_status: AgentStatus | None = None


class DependencyResponse(BaseModel):
    """Task dependency response (simplified todo for dependency display)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: Status
    priority: Priority
    due_date: date | None
    project_id: int | None = None
    project_name: str | None = None


class ParentTaskResponse(BaseModel):
    """Parent task response (simplified todo for parent link display)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    status: Status
    priority: Priority


class TodoResponse(BaseModel):
    """Todo response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    priority: Priority
    status: Status
    due_date: date | None
    deadline_type: DeadlineType = DeadlineType.preferred
    project_id: int | None
    project_name: str | None = None
    project_color: str | None = None
    tags: list[str]
    context: str | None
    estimated_hours: float | None
    actual_hours: float | None
    position: int
    parent_id: int | None = None
    parent_task: ParentTaskResponse | None = None
    subtasks: list[SubtaskResponse] = Field(default_factory=list)
    # Task dependencies
    dependencies: list[DependencyResponse] = Field(default_factory=list)
    dependents: list[DependencyResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None
    # Agent fields
    agent_actionable: bool | None = None
    action_type: ActionType | None = None
    autonomy_tier: int | None = None
    agent_status: AgentStatus | None = None
    agent_notes: str | None = None
    blocking_reason: str | None = None


# Helper functions
def _build_dependency_response(
    todo: Todo, project_name: str | None = None
) -> DependencyResponse:
    """Build DependencyResponse from Todo model.

    Args:
        todo: Todo model instance
        project_name: Optional project name

    Returns:
        DependencyResponse with key fields
    """
    return DependencyResponse(
        id=todo.id,
        title=todo.title,
        status=todo.status,
        priority=todo.priority,
        due_date=todo.due_date,
        project_id=todo.project_id,
        project_name=project_name,
    )


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
        deadline_type=subtask.deadline_type,
        estimated_hours=float(subtask.estimated_hours)
        if subtask.estimated_hours
        else None,
        actual_hours=float(subtask.actual_hours) if subtask.actual_hours else None,
        position=subtask.position,
        created_at=subtask.created_at,
        updated_at=subtask.updated_at,
        agent_actionable=subtask.agent_actionable,
        action_type=subtask.action_type,
        autonomy_tier=subtask.autonomy_tier,
        agent_status=subtask.agent_status,
    )


def _build_todo_response(
    todo: Todo,
    project_name: str | None = None,
    project_color: str | None = None,
    subtasks: list[Todo] | None = None,
    dependencies: list[tuple[Todo, str | None]] | None = None,
    dependents: list[tuple[Todo, str | None]] | None = None,
    parent_task: Todo | None = None,
) -> TodoResponse:
    """Build TodoResponse from Todo model with optional project info.

    Args:
        todo: Todo model instance
        project_name: Optional project name
        project_color: Optional project color
        subtasks: Optional list of subtask Todo instances
        dependencies: Optional list of (Todo, project_name) tuples
        dependents: Optional list of (Todo, project_name) tuples
        parent_task: Optional parent Todo instance

    Returns:
        TodoResponse with all fields populated
    """
    subtask_responses = []
    if subtasks:
        subtask_responses = [
            _build_subtask_response(s) for s in subtasks if s.deleted_at is None
        ]

    dependency_responses = []
    if dependencies:
        dependency_responses = [
            _build_dependency_response(dep, proj_name)
            for dep, proj_name in dependencies
            if dep.deleted_at is None
        ]

    dependent_responses = []
    if dependents:
        dependent_responses = [
            _build_dependency_response(dep, proj_name)
            for dep, proj_name in dependents
            if dep.deleted_at is None
        ]

    parent_task_response = None
    if parent_task:
        parent_task_response = ParentTaskResponse(
            id=parent_task.id,
            title=parent_task.title,
            status=parent_task.status,
            priority=parent_task.priority,
        )

    return TodoResponse(
        id=todo.id,
        title=todo.title,
        description=todo.description,
        priority=todo.priority,
        status=todo.status,
        due_date=todo.due_date,
        deadline_type=todo.deadline_type,
        project_id=todo.project_id,
        project_name=project_name,
        project_color=project_color,
        tags=todo.tags or [],
        context=todo.context,
        estimated_hours=float(todo.estimated_hours) if todo.estimated_hours else None,
        actual_hours=float(todo.actual_hours) if todo.actual_hours else None,
        position=todo.position,
        parent_id=todo.parent_id,
        parent_task=parent_task_response,
        subtasks=subtask_responses,
        dependencies=dependency_responses,
        dependents=dependent_responses,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
        agent_actionable=todo.agent_actionable,
        action_type=todo.action_type,
        autonomy_tier=todo.autonomy_tier,
        agent_status=todo.agent_status,
        agent_notes=todo.agent_notes,
        blocking_reason=todo.blocking_reason,
    )


async def _resolve_category_to_project(
    db: "DbSession", category: str, user_id: int
) -> int | None:
    """Resolve a category name to a project_id for the given user.

    Returns:
        The project ID if found, None otherwise.
    """
    result = await db.execute(
        select(Project).where(Project.name == category, Project.user_id == user_id)
    )
    project = result.scalar_one_or_none()
    return project.id if project else None


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
) -> tuple[ActionType | None, bool | None, int | None]:
    """Infer action type, agent actionability, and autonomy tier from task.

    Uses keyword matching to classify tasks. Returns (None, None, None) if no
    pattern matches, allowing the agent to classify later via LLM.

    Args:
        title: Task title
        description: Optional task description

    Returns:
        Tuple of (action_type, agent_actionable, autonomy_tier) or
        (None, None, None) if unknown.
    """
    text = f"{title} {description or ''}".lower()

    for action_type, (keywords, actionable) in ACTION_PATTERNS.items():
        if any(keyword in text for keyword in keywords):
            # Get default autonomy tier from mapping
            default_tier = ACTION_TYPE_DEFAULT_TIER.get(action_type)
            tier_value = default_tier.value if default_tier else None
            return action_type, actionable, tier_value

    return None, None, None  # Unknown - agent can classify later


def _apply_todo_filters(
    query,
    *,
    status: str | None,
    project_id: int | None,
    category: str | None,
    start_date: date | None,
    end_date: date | None,
    no_due_date: bool,
    parent_id: int | None,
    deadline_type: str | None,
    order_by: str | None,
):
    """Apply filtering and ordering to a todo list query."""
    # Filter by parent_id - if not specified, only show root-level todos
    if parent_id is not None:
        query = query.where(Todo.parent_id == parent_id)
    else:
        query = query.where(Todo.parent_id.is_(None))

    if status and status != "all":
        if status == "overdue":
            query = query.where(
                and_(
                    Todo.due_date < datetime.now(tz=UTC).date(),
                    Todo.status != Status.completed,
                )
            )
        else:
            query = query.where(Todo.status == status)

    if project_id:
        query = query.where(Todo.project_id == project_id)

    if category:
        query = query.where(Project.name == category)

    if no_due_date:
        query = query.where(Todo.due_date.is_(None))
    else:
        if start_date:
            query = query.where(Todo.due_date >= start_date)
        if end_date:
            query = query.where(Todo.due_date <= end_date)

    if deadline_type:
        query = query.where(Todo.deadline_type == deadline_type)

    # Deadline type strictness ordering: flexible < preferred < firm < hard
    _deadline_type_order = {"flexible": 0, "preferred": 1, "firm": 2, "hard": 3}

    if order_by == "position":
        query = query.order_by(Todo.position, Todo.created_at)
    elif order_by == "deadline_type":
        query = query.order_by(
            case(
                _deadline_type_order,
                value=Todo.deadline_type,
                else_=1,
            ).desc(),
            Todo.due_date.asc().nulls_last(),
        )
    else:
        query = query.order_by(Todo.due_date.asc().nulls_last(), Todo.priority.desc())

    return query


async def _fetch_subtasks_map(
    db: "DbSession", todo_ids: list[int], user_id: int
) -> dict[int, list[Todo]]:
    """Fetch subtasks for a list of todo IDs, grouped by parent_id."""
    if not todo_ids:
        return {}

    subtasks_query = (
        select(Todo)
        .where(Todo.parent_id.in_(todo_ids))
        .where(Todo.user_id == user_id)
        .where(Todo.deleted_at.is_(None))
        .order_by(Todo.position, Todo.created_at.asc())
    )
    subtasks_result = await db.execute(subtasks_query)
    subtasks_map: dict[int, list[Todo]] = {}
    for subtask in subtasks_result.scalars().all():
        if subtask.parent_id is not None:
            subtasks_map.setdefault(subtask.parent_id, []).append(subtask)
    return subtasks_map


@router.get("")
async def list_todos(
    user: CurrentUserFlexible,
    db: DbSession,
    status: str | None = Query(None),
    project_id: int | None = Query(None),
    category: str | None = Query(None),
    start_date: date | None = Query(None),  # noqa: B008
    end_date: date | None = Query(None),  # noqa: B008
    no_due_date: bool = Query(False),
    parent_id: int | None = Query(None),
    deadline_type: Literal["flexible", "preferred", "firm", "hard"] | None = Query(
        None, description="Filter by deadline type"
    ),
    include_subtasks: bool = Query(False),
    order_by: Literal["position", "due_date", "deadline_type"] | None = Query(
        None, description="Sort order"
    ),
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

    query = _apply_todo_filters(
        query,
        status=status,
        project_id=project_id,
        category=category,
        start_date=start_date,
        end_date=end_date,
        no_due_date=no_due_date,
        parent_id=parent_id,
        deadline_type=deadline_type,
        order_by=order_by,
    )

    result = await db.execute(query)
    rows = result.all()

    subtasks_map: dict[int, list[Todo]] = {}
    if include_subtasks:
        subtasks_map = await _fetch_subtasks_map(
            db, [row[0].id for row in rows], user.id
        )

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
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Create a new todo or subtask.

    To create a subtask, provide the parent_id of the parent todo.
    """
    # Resolve category name to project_id
    if request.category and not request.project_id:
        project_id = await _resolve_category_to_project(db, request.category, user.id)
        if project_id:
            request.project_id = project_id

    # Verify parent todo exists and belongs to user if parent_id is provided
    if request.parent_id:
        parent = await get_resource_for_user(
            db, Todo, request.parent_id, user.id, errors.todo_not_found
        )

        # Prevent nested subtasks (subtasks of subtasks)
        if parent.parent_id is not None:
            raise errors.validation(
                "Cannot create subtasks of subtasks. "
                "Only one level of nesting is allowed."
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
    autonomy_tier = request.autonomy_tier
    if agent_actionable is None or action_type is None or autonomy_tier is None:
        inferred_type, inferred_actionable, inferred_tier = infer_action_type(
            request.title, request.description
        )
        if action_type is None:
            action_type = inferred_type
        if agent_actionable is None:
            agent_actionable = inferred_actionable
        if autonomy_tier is None:
            autonomy_tier = inferred_tier

    todo = Todo(
        user_id=user.id,
        title=request.title,
        description=request.description,
        priority=request.priority,
        status=request.status,
        due_date=request.due_date,
        deadline_type=request.deadline_type,
        project_id=request.project_id,
        tags=request.tags,
        context=request.context,
        estimated_hours=request.estimated_hours,
        parent_id=request.parent_id,
        position=position,
        agent_actionable=agent_actionable,
        action_type=action_type,
        autonomy_tier=autonomy_tier,
    )
    db.add(todo)
    await db.flush()
    await db.refresh(todo)

    project_name, project_color = await get_project_info(db, todo.project_id, user.id)
    return {"data": _build_todo_response(todo, project_name, project_color)}


def _validate_batch_dependency_graph(todos: list[TodoCreate]) -> None:
    """Validate that depends_on references don't form circular dependencies.

    Uses Kahn's algorithm (topological sort) to detect cycles in the
    dependency graph defined by the batch's depends_on indices.

    Raises:
        errors.validation: If a circular dependency is detected.
    """
    from collections import deque

    n = len(todos)
    # Build adjacency list and in-degree count
    # Edge: dep_idx -> i means "i depends on dep_idx" (dep_idx must come first)
    adj: dict[int, list[int]] = {i: [] for i in range(n)}
    in_degree = [0] * n

    for i, item in enumerate(todos):
        if item.depends_on:
            for dep_idx in item.depends_on:
                adj[dep_idx].append(i)
                in_degree[i] += 1

    # Kahn's algorithm: start with nodes that have no dependencies
    queue: deque[int] = deque()
    for i in range(n):
        if in_degree[i] == 0:
            queue.append(i)

    visited_count = 0
    while queue:
        node = queue.popleft()
        visited_count += 1
        for neighbor in adj[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited_count < n:
        raise errors.validation(
            "Circular dependency detected in batch depends_on references"
        )


@router.post("/batch", status_code=201)
async def batch_create_todos(
    request: BatchTodoCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Create multiple todos in a single request.

    Accepts up to 50 todo objects. All todos are created atomically—if any
    validation fails, none are created. Validation runs for all items before
    any database writes occur.

    Each task can include a ``depends_on`` field with a list of 0-based indices
    referring to other tasks in the same batch. After all tasks are created,
    the dependency relationships are established. Indices are validated for
    bounds, self-references, and circular dependencies within the batch.

    Tasks may reference other tasks in the same batch as parents via the
    ``parent_index`` field (0-based index).  Parents must appear before
    children in the list, and only one level of nesting is allowed.
    ``parent_index`` and ``parent_id`` are mutually exclusive per task.
    """
    batch_size = len(request.todos)

    # Phase 0: Validate depends_on indices before any database work
    for i, item in enumerate(request.todos):
        if item.depends_on:
            for dep_idx in item.depends_on:
                if dep_idx < 0 or dep_idx >= batch_size:
                    raise errors.validation(
                        f"Task at index {i}: depends_on index {dep_idx} "
                        f"is out of bounds (batch size: {batch_size})"
                    )
                if dep_idx == i:
                    raise errors.validation(
                        f"Task at index {i}: cannot depend on itself "
                        f"(self-reference at index {dep_idx})"
                    )

    # Check for circular dependencies within the batch using topological sort
    _validate_batch_dependency_graph(request.todos)

    # Phase 1: Validate all items and prepare Todo objects before any writes.
    # Items with parent_index skip parent_id assignment here — it's set in
    # phase 3 after all items have been flushed and have real IDs.
    prepared: list[Todo] = []
    # Track which batch index each prepared Todo corresponds to, and which
    # items need parent_index resolution.
    parent_index_map: dict[int, int] = {}  # prepared idx -> parent batch idx

    for i, item in enumerate(request.todos):
        # Resolve category name to project_id
        if item.category and not item.project_id:
            project_id = await _resolve_category_to_project(db, item.category, user.id)
            if project_id:
                item.project_id = project_id

        # Verify parent todo exists and belongs to user (only for parent_id,
        # not parent_index which references items within this batch)
        if item.parent_id:
            parent = await get_resource_for_user(
                db, Todo, item.parent_id, user.id, errors.todo_not_found
            )
            if parent.parent_id is not None:
                raise errors.validation(
                    "Cannot create subtasks of subtasks. "
                    "Only one level of nesting is allowed."
                )

        # Record parent_index for later resolution
        if item.parent_index is not None:
            parent_index_map[i] = item.parent_index

        # Auto-assign position if not provided.
        # For parent_index items, parent_id is not yet known so we pass None
        # and positions will be recalculated in phase 3.
        effective_parent_id = item.parent_id  # None for parent_index items
        position = item.position
        if position is None:
            position = await get_next_position(
                db, Todo, user.id, parent_id=effective_parent_id
            )

        # Infer agent fields if not provided
        agent_actionable = item.agent_actionable
        action_type = item.action_type
        autonomy_tier = item.autonomy_tier
        if agent_actionable is None or action_type is None or autonomy_tier is None:
            inferred_type, inferred_actionable, inferred_tier = infer_action_type(
                item.title, item.description
            )
            if action_type is None:
                action_type = inferred_type
            if agent_actionable is None:
                agent_actionable = inferred_actionable
            if autonomy_tier is None:
                autonomy_tier = inferred_tier

        prepared.append(
            Todo(
                user_id=user.id,
                title=item.title,
                description=item.description,
                priority=item.priority,
                status=item.status,
                due_date=item.due_date,
                deadline_type=item.deadline_type,
                project_id=item.project_id,
                tags=item.tags,
                context=item.context,
                estimated_hours=item.estimated_hours,
                parent_id=item.parent_id,
                position=position,
                agent_actionable=agent_actionable,
                action_type=action_type,
                autonomy_tier=autonomy_tier,
            )
        )

    # Phase 2: All validation passed — write to database
    for todo in prepared:
        db.add(todo)
        await db.flush()
        await db.refresh(todo)

    # Phase 3: Resolve parent_index references now that all items have IDs
    for child_idx, parent_batch_idx in parent_index_map.items():
        child_todo = prepared[child_idx]
        parent_todo = prepared[parent_batch_idx]
        child_todo.parent_id = parent_todo.id
        # Recalculate position under the new parent
        child_todo.position = await get_next_position(
            db, Todo, user.id, parent_id=parent_todo.id
        )
        await db.flush()
        await db.refresh(child_todo)

    # Phase 4: Create dependency relationships using the now-assigned IDs
    for i, item in enumerate(request.todos):
        if item.depends_on:
            for dep_idx in item.depends_on:
                await db.execute(
                    task_dependencies.insert().values(
                        dependent_id=prepared[i].id,
                        dependency_id=prepared[dep_idx].id,
                    )
                )
    await db.flush()

    # Phase 5: Build responses
    created: list[TodoResponse] = []
    for todo in prepared:
        project_name, project_color = await get_project_info(
            db, todo.project_id, user.id
        )
        created.append(_build_todo_response(todo, project_name, project_color))

    return {"data": created, "meta": {"count": len(created)}}


@router.get("/{todo_id}")
async def get_todo(
    todo_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Get a todo by ID with its subtasks and dependencies."""
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

    # Fetch parent task if this is a subtask
    parent_task = None
    if todo.parent_id:
        parent_result = await db.execute(
            select(Todo).where(
                Todo.id == todo.parent_id,
                Todo.user_id == user.id,
                Todo.deleted_at.is_(None),
            )
        )
        parent_task = parent_result.scalar_one_or_none()

    # Fetch subtasks
    subtasks_result = await db.execute(
        select(Todo)
        .where(Todo.parent_id == todo_id, Todo.deleted_at.is_(None))
        .order_by(Todo.created_at.asc())
    )
    subtasks = list(subtasks_result.scalars().all())

    # Fetch dependencies (tasks this todo depends on)
    dependencies_result = await db.execute(
        select(Todo, Project.name.label("project_name"))
        .outerjoin(Project, Todo.project_id == Project.id)
        .join(
            task_dependencies,
            Todo.id == task_dependencies.c.dependency_id,
        )
        .where(
            task_dependencies.c.dependent_id == todo_id,
            Todo.deleted_at.is_(None),
        )
    )
    dependencies = [(row[0], row.project_name) for row in dependencies_result.all()]

    # Fetch dependents (tasks that depend on this todo)
    dependents_result = await db.execute(
        select(Todo, Project.name.label("project_name"))
        .outerjoin(Project, Todo.project_id == Project.id)
        .join(
            task_dependencies,
            Todo.id == task_dependencies.c.dependent_id,
        )
        .where(
            task_dependencies.c.dependency_id == todo_id,
            Todo.deleted_at.is_(None),
        )
    )
    dependents = [(row[0], row.project_name) for row in dependents_result.all()]

    return {
        "data": _build_todo_response(
            todo,
            project_name=row.project_name,
            project_color=row.project_color,
            subtasks=subtasks,
            dependencies=dependencies,
            dependents=dependents,
            parent_task=parent_task,
        )
    }


@router.put("/{todo_id}")
async def update_todo(
    todo_id: int,
    request: TodoUpdate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Update a todo."""
    todo = await get_resource_for_user(
        db, Todo, todo_id, user.id, errors.todo_not_found, check_deleted=False
    )

    # Resolve category name to project_id
    update_data = request.model_dump(exclude_unset=True)
    if "category" in update_data:
        category = update_data.pop("category")
        if category and "project_id" not in update_data:
            project_id = await _resolve_category_to_project(db, category, user.id)
            if project_id:
                update_data["project_id"] = project_id

    # Verify parent_id authorization if being updated
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

    # Clear completed_date when status changes away from completed
    if "status" in update_data and update_data["status"] != Status.completed:
        todo.completed_date = None

    # Commit the changes
    await db.commit()
    await db.refresh(todo)

    project_name, project_color = await get_project_info(db, todo.project_id, user.id)
    return {"data": _build_todo_response(todo, project_name, project_color)}


@router.put("")
async def bulk_update_todos(
    request: BulkUpdateRequest,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Bulk update todos."""
    todos_dict = await get_resources_for_user(db, Todo, request.ids, user.id)
    todos = list(todos_dict.values())

    # Resolve category name to project_id
    update_data = request.updates.model_dump(exclude_unset=True)
    if "category" in update_data:
        category = update_data.pop("category")
        if category and "project_id" not in update_data:
            project_id = await _resolve_category_to_project(db, category, user.id)
            if project_id:
                update_data["project_id"] = project_id

    # Verify parent_id authorization if being updated
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
    user: CurrentUserFlexible,
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
    user: CurrentUserFlexible,
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
    user: CurrentUserFlexible,
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
    user: CurrentUserFlexible,
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
    user: CurrentUserFlexible,
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


# Dependency endpoints
class DependencyCreate(BaseModel):
    """Add dependency request."""

    dependency_id: int = Field(..., description="ID of the task this task depends on")


async def _check_circular_dependency(
    db: DbSession, dependent_id: int, dependency_id: int
) -> bool:
    """Check if adding this dependency would create a circular dependency.

    Uses breadth-first search to traverse the dependency graph and check if
    the dependent task is reachable from the dependency task (which would
    create a cycle).

    This implementation fetches the entire dependency graph upfront in a single
    query to avoid N+1 query performance issues.

    Args:
        db: Database session
        dependent_id: The task that will depend on another
        dependency_id: The task being depended upon

    Returns:
        True if adding this dependency would create a cycle, False otherwise
    """
    # Fetch entire dependency graph in a single query
    result = await db.execute(select(task_dependencies))
    all_deps = result.all()

    # Build adjacency list: dependent_id -> [dependency_ids]
    graph: dict[int, list[int]] = {}
    for row in all_deps:
        dep_id = row.dependent_id
        if dep_id not in graph:
            graph[dep_id] = []
        graph[dep_id].append(row.dependency_id)

    # BFS to find if dependent_id is reachable from dependency_id
    visited: set[int] = set()
    queue = [dependency_id]

    while queue:
        current_id = queue.pop(0)
        if current_id == dependent_id:
            return True  # Found a cycle

        if current_id in visited:
            continue
        visited.add(current_id)

        # Get all tasks that the current task depends on (from in-memory graph)
        for next_id in graph.get(current_id, []):
            if next_id not in visited:
                queue.append(next_id)

    return False


@router.get("/{todo_id}/dependencies")
async def list_dependencies(
    todo_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> ListResponse[DependencyResponse]:
    """List all dependencies for a todo (tasks it depends on)."""
    # Verify todo exists and belongs to user
    await get_resource_for_user(db, Todo, todo_id, user.id, errors.todo_not_found)

    # Fetch dependencies
    result = await db.execute(
        select(Todo, Project.name.label("project_name"))
        .outerjoin(Project, Todo.project_id == Project.id)
        .join(
            task_dependencies,
            Todo.id == task_dependencies.c.dependency_id,
        )
        .where(
            task_dependencies.c.dependent_id == todo_id,
            Todo.deleted_at.is_(None),
        )
    )
    dependencies = [
        _build_dependency_response(row[0], row.project_name) for row in result.all()
    ]

    return ListResponse(data=dependencies, meta={"count": len(dependencies)})


@router.post("/{todo_id}/dependencies", status_code=201)
async def add_dependency(
    todo_id: int,
    request: DependencyCreate,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Add a dependency to a todo.

    The dependency_id specifies the task that must be completed before this task.

    This endpoint handles race conditions by:
    1. Relying on database primary key constraint for duplicate detection
    2. Checking circular dependencies before insert (best effort)
    3. Catching IntegrityError to return appropriate error responses
    """
    from sqlalchemy.exc import IntegrityError

    # Verify todo exists and belongs to user
    await get_resource_for_user(db, Todo, todo_id, user.id, errors.todo_not_found)

    # Verify dependency todo exists and belongs to user
    dependency = await get_resource_for_user(
        db, Todo, request.dependency_id, user.id, errors.todo_not_found
    )

    # Prevent self-dependency
    if todo_id == request.dependency_id:
        raise errors.self_dependency()

    # Check for circular dependency before attempting insert
    # Note: There's still a small race window, but circular deps are caught
    # at query time and don't corrupt data (just create invalid state)
    if await _check_circular_dependency(db, todo_id, request.dependency_id):
        raise errors.circular_dependency()

    # Try to add the dependency - rely on DB constraint for duplicate detection
    try:
        await db.execute(
            task_dependencies.insert().values(
                dependent_id=todo_id,
                dependency_id=request.dependency_id,
            )
        )
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise errors.dependency_exists() from None

    project_name, _ = await get_project_info(db, dependency.project_id, user.id)
    return {"data": _build_dependency_response(dependency, project_name)}


@router.delete("/{todo_id}/dependencies/{dependency_id}")
async def remove_dependency(
    todo_id: int,
    dependency_id: int,
    user: CurrentUserFlexible,
    db: DbSession,
) -> dict:
    """Remove a dependency from a todo."""
    # Verify todo exists and belongs to user
    await get_resource_for_user(db, Todo, todo_id, user.id, errors.todo_not_found)

    # Check if dependency exists
    existing = await db.execute(
        select(task_dependencies).where(
            task_dependencies.c.dependent_id == todo_id,
            task_dependencies.c.dependency_id == dependency_id,
        )
    )
    if not existing.first():
        raise errors.dependency_not_found()

    # Remove the dependency
    await db.execute(
        task_dependencies.delete().where(
            task_dependencies.c.dependent_id == todo_id,
            task_dependencies.c.dependency_id == dependency_id,
        )
    )

    return {"data": {"deleted": True, "dependency_id": dependency_id}}
