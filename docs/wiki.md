# Wiki Feature

The wiki is a per-user knowledge base built into TaskManager. Pages are written in Markdown, organized in a hierarchy up to 3 levels deep, tagged for filtering, and can be linked to tasks bidirectionally. Every edit is recorded as a revision so the full history of a page is preserved.

## Contents

- [Data model](#data-model)
- [API endpoints](#api-endpoints)
  - [Pages](#pages)
  - [Revisions](#revisions)
  - [Task linking](#task-linking)
  - [Subscriptions](#subscriptions)
  - [Todo-side endpoint](#todo-side-endpoint)
- [MCP tools](#mcp-tools)
- [Frontend](#frontend)
- [Agent behavior guide](#agent-behavior-guide)

---

## Data model

### WikiPage

| Field            | Type                | Notes                                              |
|------------------|---------------------|----------------------------------------------------|
| `id`             | integer             | Primary key                                        |
| `user_id`        | integer             | Owner (pages are private per user)                 |
| `parent_id`      | integer \| null     | Enables nested hierarchy (max depth 3)             |
| `title`          | string (max 500)    |                                                    |
| `slug`           | string (max 200)    | URL-safe identifier, unique per user               |
| `content`        | text                | Markdown, max 500,000 characters                   |
| `tags`           | string[]            | JSONB array, max 20 tags of max 50 chars each      |
| `revision_number`| integer             | Increments on every update                         |
| `created_at`     | timestamp with tz   |                                                    |
| `updated_at`     | timestamp with tz   |                                                    |
| `deleted_at`     | timestamp \| null   | Soft delete (pages and all descendants)            |

**Slug rules:**
- Must be lowercase letters, numbers, and hyphens only (`^[a-z0-9]+(?:-[a-z0-9]+)*$`)
- Max 200 characters
- Cannot be purely numeric
- Reserved values: `new`, `resolve`, `tree`
- If a slug collides with an existing page for the same user, a numeric suffix is appended automatically (`my-page-2`, `my-page-3`, …)
- When a title is updated without providing an explicit slug, the slug is regenerated from the new title

### WikiPageRevision

| Field             | Type              | Notes                                    |
|-------------------|-------------------|------------------------------------------|
| `id`              | integer           |                                          |
| `wiki_page_id`    | integer           |                                          |
| `title`           | string            | State of title at time of revision       |
| `slug`            | string            | State of slug at time of revision        |
| `content`         | text              | State of content at time of revision     |
| `revision_number` | integer           | Matches the page's revision_number before the update |
| `created_at`      | timestamp with tz |                                          |

A revision is saved automatically before every update to a page.

### todo_wiki_links

Many-to-many join table connecting `todos` and `wiki_pages`. Each pair is unique.

---

## API endpoints

All wiki endpoints require authentication (session cookie or OAuth Bearer token).

Base path: `/api/wiki`

### Pages

#### List pages

```
GET /api/wiki
```

Query parameters:

| Parameter   | Type    | Description                                          |
|-------------|---------|------------------------------------------------------|
| `q`         | string  | Full-text search over title and content              |
| `tag`       | string  | Filter to pages that have this exact tag             |
| `parent_id` | integer | Filter by parent. Use `0` to list only root pages    |

Response:
```json
{
  "data": [
    {
      "id": 1,
      "title": "Meeting Notes",
      "slug": "meeting-notes",
      "parent_id": null,
      "tags": ["meetings", "q1"],
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-15T10:30:00Z",
      "content_snippet": "...matched text around the query..."
    }
  ],
  "meta": { "count": 1 }
}
```

`content_snippet` is only included when `q` is provided.

Results are ordered by `updated_at` descending.

---

#### Create a page

```
POST /api/wiki
```

Request body:

| Field       | Type     | Required | Description                                            |
|-------------|----------|----------|--------------------------------------------------------|
| `title`     | string   | Yes      | 1–500 characters                                       |
| `content`   | string   | No       | Markdown content, default `""`                         |
| `slug`      | string   | No       | Custom slug; auto-generated from title if omitted      |
| `parent_id` | integer  | No       | Parent page ID; max hierarchy depth is 3 levels        |
| `tags`      | string[] | No       | Up to 20 tags                                          |

Response: `201 Created` with the full page object including `ancestors`, `children`, `slug_modified`, and `requested_slug` fields.

If the chosen slug was already in use, the response includes `"slug_modified": true` and `"requested_slug": "<original>"` so callers know the actual slug that was assigned.

---

#### Get a page

```
GET /api/wiki/{slug_or_id}
```

Accepts either a slug string (e.g., `meeting-notes`) or a numeric ID. Numeric IDs are tried first; if no match is found, the value is treated as a slug.

Response includes `ancestors` (root-first list) and `children` (with their own child counts).

---

#### Update a page

```
PUT /api/wiki/{page_id}
```

Request body (all fields optional):

| Field          | Type     | Description                                                      |
|----------------|----------|------------------------------------------------------------------|
| `title`        | string   | New title; also re-generates slug unless `slug` is provided      |
| `content`      | string   | New content (replaces existing unless `append` is `true`)        |
| `slug`         | string   | New explicit slug                                                |
| `append`       | boolean  | If `true`, appends `content` to existing content (default false) |
| `parent_id`    | integer  | Move this page under a new parent                               |
| `remove_parent`| boolean  | Remove parent and promote page to root (mutually exclusive with `parent_id`) |
| `tags`         | string[] | Replace tag list entirely                                        |

The previous state of the page is saved as a revision before the update is applied.

---

#### Delete a page

```
DELETE /api/wiki/{page_id}
```

Soft-deletes the page and all of its descendants. Deleted pages do not appear in listings and cannot be fetched, but the page record and its revision history are preserved in the database. Users should be aware that deleting a page does not immediately erase the content from storage.

Response:
```json
{ "data": { "deleted": true, "id": 42 } }
```

---

#### Move a page

```
PATCH /api/wiki/{page_id}/move
```

Request body:

| Field      | Type           | Description                                           |
|------------|----------------|-------------------------------------------------------|
| `parent_id`| integer \| null| New parent ID, or `null` to make the page a root page |

This is a convenience endpoint that only changes the parent without requiring a full update payload. Depth validation still applies.

---

#### Get the full tree

```
GET /api/wiki/tree
```

Returns all of the user's pages as a nested tree, ordered alphabetically at each level.

Response:
```json
{
  "data": [
    {
      "id": 1,
      "title": "Guides",
      "slug": "guides",
      "tags": [],
      "updated_at": "2026-01-15T10:30:00Z",
      "children": [
        {
          "id": 2,
          "title": "Getting Started",
          "slug": "getting-started",
          "tags": ["onboarding"],
          "updated_at": "2026-01-10T08:00:00Z",
          "children": []
        }
      ]
    }
  ]
}
```

---

#### Resolve titles to slugs

```
GET /api/wiki/resolve?titles=Page+One,Page+Two
```

Batch-resolves page titles to their slugs. Returns a map of `{ title: slug | null }` — `null` means no page with that exact title was found.

Accepts up to 50 titles in a single request.

Used by the frontend to resolve `[[Page Title]]` wiki-link syntax in Markdown.

---

### Revisions

#### List revisions

```
GET /api/wiki/{page_id}/revisions
```

Returns revision summaries (without content) ordered newest-first.

Response:
```json
{
  "data": [
    {
      "id": 5,
      "wiki_page_id": 1,
      "title": "Meeting Notes",
      "slug": "meeting-notes",
      "revision_number": 3,
      "created_at": "2026-01-15T10:30:00Z"
    }
  ],
  "meta": { "count": 1 }
}
```

#### Get a specific revision

```
GET /api/wiki/{page_id}/revisions/{revision_number}
```

Returns the full revision including `content`.

---

### Task linking

#### Link a task

```
POST /api/wiki/{page_id}/link-task
```

Request body:
```json
{ "todo_id": 123 }
```

Returns the linked task summary. Returns an error if the link already exists.

#### Batch link tasks

```
POST /api/wiki/{page_id}/link-tasks
```

Request body:
```json
{ "todo_ids": [1, 2, 3] }
```

Links up to 100 tasks in one request. Silently handles already-linked tasks.

Response:
```json
{
  "data": {
    "linked": [1, 2],
    "already_linked": [3],
    "not_found": []
  }
}
```

#### Unlink a task

```
DELETE /api/wiki/{page_id}/link-task/{todo_id}
```

Returns `{ "data": { "deleted": true, "page_id": ..., "todo_id": ... } }`.

#### List linked tasks

```
GET /api/wiki/{page_id}/linked-tasks
```

Returns all tasks linked to the page with fields: `id`, `title`, `status`, `priority`, `due_date`.

---

### Subscriptions

Subscribe to receive in-app notifications when a page (and optionally its descendants) is created, updated, or deleted.

#### Get subscription status

```
GET /api/wiki/{page_id}/subscription
```

Response:
```json
{
  "data": {
    "subscribed": true,
    "subscription": {
      "id": 7,
      "wiki_page_id": 1,
      "include_children": true,
      "created_at": "2026-01-01T00:00:00Z"
    }
  }
}
```

#### Subscribe

```
POST /api/wiki/{page_id}/subscription
```

Request body:
```json
{ "include_children": true }
```

- `include_children: true` (default) — also receive notifications when child pages change.
- Calling this endpoint again on an already-subscribed page updates `include_children` and returns `200` instead of `201`.

#### Unsubscribe

```
DELETE /api/wiki/{page_id}/subscription
```

---

### Todo-side endpoint

#### List wiki pages linked to a task

```
GET /api/todos/{todo_id}/wiki-pages
```

Returns wiki page summaries linked to the given task, ordered alphabetically by title.

---

## MCP tools

The MCP resource server exposes the following wiki tools to AI assistants. All tools require OAuth authentication.

### Resource

```
taskmanager://wiki/pages
```

Lists all wiki pages for the authenticated user (id, title, slug, timestamps). Use this resource for a complete listing without any search filter.

### Tools

#### `search_wiki_pages`

Search wiki pages by title or content.

| Parameter | Type   | Required | Description                      |
|-----------|--------|----------|----------------------------------|
| `q`       | string | Yes      | Query to match against title/content |

Returns a `pages` array with page summaries.

---

#### `create_wiki_page`

Create a new wiki page.

| Parameter   | Type    | Required | Description                                                 |
|-------------|---------|----------|-------------------------------------------------------------|
| `title`     | string  | Yes      | Page title (1–500 characters)                               |
| `content`   | string  | No       | Markdown content (default `""`)                             |
| `slug`      | string  | No       | Custom slug; auto-generated from title if omitted           |
| `parent_id` | integer | No       | Parent page ID. Max depth is 3 levels.                      |

Returns the created page object including `id`, `title`, `slug`, `content`, `created_at`.

---

#### `get_wiki_page`

Retrieve a wiki page by slug or numeric ID.

| Parameter    | Type   | Required | Description                                 |
|--------------|--------|----------|---------------------------------------------|
| `slug_or_id` | string | Yes      | Page slug (`"meeting-notes"`) or ID (`"42"`) |

Returns the full page object including content.

---

#### `update_wiki_page`

Update an existing wiki page.

| Parameter      | Type    | Required | Description                                                    |
|----------------|---------|----------|----------------------------------------------------------------|
| `page_id`      | integer | Yes      | Page ID to update                                              |
| `title`        | string  | No       | New title                                                      |
| `content`      | string  | No       | New content (replaces existing unless `append` is `true`)      |
| `slug`         | string  | No       | New slug                                                       |
| `append`       | boolean | No       | Append `content` to existing content instead of replacing (default `false`) |
| `parent_id`    | integer | No       | Move under a new parent                                        |
| `remove_parent`| boolean | No       | Promote to root page (mutually exclusive with `parent_id`)     |

Returns the updated page with the new `revision_number`.

---

#### `delete_wiki_page`

Soft-delete a wiki page and all its descendants.

| Parameter | Type    | Required | Description       |
|-----------|---------|----------|-------------------|
| `page_id` | integer | Yes      | Page ID to delete |

---

#### `link_wiki_page_to_task`

Link a wiki page to a task, creating a bidirectional association.

| Parameter | Type    | Required | Description                            |
|-----------|---------|----------|----------------------------------------|
| `page_id` | integer | Yes      | Wiki page ID                           |
| `task_id` | string  | Yes      | Task ID in `"task_123"` or `"123"` format |

---

#### `get_wiki_page_linked_tasks`

Get all tasks linked to a wiki page.

| Parameter | Type    | Required | Description  |
|-----------|---------|----------|--------------|
| `page_id` | integer | Yes      | Wiki page ID |

Returns a `tasks` array with `id` (prefixed `task_N`), `title`, `status`, `priority`, `due_date`.

---

#### `get_task_wiki_pages`

Get all wiki pages linked to a task.

| Parameter | Type   | Required | Description                            |
|-----------|--------|----------|----------------------------------------|
| `task_id` | string | Yes      | Task ID in `"task_123"` or `"123"` format |

Returns a `pages` array with page summaries.

---

#### `batch_link_wiki_page_to_tasks`

Link a wiki page to multiple tasks in one call.

| Parameter  | Type     | Required | Description                                   |
|------------|----------|----------|-----------------------------------------------|
| `page_id`  | integer  | Yes      | Wiki page ID                                  |
| `task_ids` | string[] | Yes      | Task IDs in `"task_123"` or `"123"` format    |

Response reports `linked`, `already_linked`, and `not_found` arrays.

---

#### `create_tasks` — wiki integration

The `create_tasks` batch tool accepts an optional `wiki_page_id` parameter. When provided, every task created in the batch is automatically linked to that wiki page. This eliminates the need to call `link_wiki_page_to_task` separately for each task.

```
create_tasks(
    tasks=[...],
    wiki_page_id=42
)
```

The response includes `wiki_page_id` and `wiki_links_created` fields when this parameter is used.

---

#### `unified_search`

Search across tasks, wiki pages, snippets, and articles at once.

| Parameter | Type   | Required | Description                                                           |
|-----------|--------|----------|-----------------------------------------------------------------------|
| `query`   | string | Yes      | Search query                                                          |
| `types`   | string | No       | Comma-separated types to include: `task`, `wiki`, `snippet`, `article` |
| `limit`   | integer| No       | Max results per type, 1–20 (default 5)                               |

---

## Frontend

The wiki UI is available at `/wiki`.

### Routes

| Route                  | Description                                             |
|------------------------|---------------------------------------------------------|
| `/wiki`                | Index: tree view (default) or flat list when searching  |
| `/wiki/new`            | Create a new page                                       |
| `/wiki/{slug}`         | View a page                                             |
| `/wiki/{slug}/edit`    | Edit a page                                             |

### Index page (`/wiki`)

- Displays all pages as a **nested tree** by default.
- Switches to a **flat list** when a search query or tag filter is active.
- Search is debounced (300 ms) and filters by title and content.
- Tags extracted from all pages are displayed as clickable chips. Clicking a tag filters to pages with that tag and updates the URL (`?tag=<tag>`).

### Page view (`/wiki/{slug}`)

- Renders Markdown content as HTML.
- Supports `[[Page Title]]` wiki-link syntax. Links are resolved to slugs and rendered as clickable links. Links to pages that do not exist are shown with a dashed underline.
- Displays **breadcrumbs** using the page's ancestor chain.
- Lists **child pages** with their sub-page counts. A "New Child Page" button is shown for navigating to `/wiki/new?parent={page_id}`.
- Lists **linked tasks** with their status.
- Includes **Subscribe / Unsubscribe** controls. When subscribed, an additional checkbox controls whether child page changes also trigger notifications.
- Actions: **Edit**, **Move** (modal dialog), **Delete** (with confirmation step).

### Create / Edit forms (`/wiki/new`, `/wiki/{slug}/edit`)

- Fields: title, parent page selector, tags (comma-separated), Markdown content editor.
- Live **preview** toggle renders Markdown and resolves `[[wiki links]]` against existing pages.
- The `?title=` query parameter pre-fills the title (used by the wiki-link create flow).
- The `?parent=` query parameter pre-fills the parent selector.
- The parent selector only shows pages that can legally be a parent (max depth constraint is enforced in the UI by filtering the tree to depth ≤ 2; the API enforces the hard limit of 3 levels).

---

## Agent behavior guide

The following patterns describe how an AI assistant integrated via MCP should work with the wiki.

### Discovering existing content

Before creating new pages, check whether relevant content already exists:

```
# Check the resource for a full listing
GET taskmanager://wiki/pages

# Or search by topic
search_wiki_pages(q="deployment")
```

### Creating a knowledge base for a project

1. Create a parent page for the project:
   ```
   create_wiki_page(title="Project Alpha", content="Overview of Project Alpha.")
   # returns page with id=10
   ```

2. Create child pages under it:
   ```
   create_wiki_page(title="Architecture", content="...", parent_id=10)
   create_wiki_page(title="Runbook", content="...", parent_id=10)
   ```

3. Create tasks and link them all to the relevant wiki page in one call:
   ```
   create_tasks(
       tasks=[
           {"title": "Set up CI", "priority": "high"},
           {"title": "Write tests", "priority": "medium"}
       ],
       wiki_page_id=10
   )
   ```

### Appending information without overwriting

Use `append=true` to add new content to a page without replacing the existing body:

```
update_wiki_page(
    page_id=10,
    content="\n## 2026-03-03 Update\n\nNew information here.",
    append=true
)
```

This is useful for log-style pages or when recording outcomes of a meeting or task.

### Linking existing tasks to a page

```
# Link one task
link_wiki_page_to_task(page_id=10, task_id="task_42")

# Link multiple tasks at once
batch_link_wiki_page_to_tasks(page_id=10, task_ids=["task_42", "task_43", "task_44"])
```

### Cross-content search

Use `unified_search` when the user does not know what type of content they are looking for:

```
unified_search(query="deployment checklist", types="task,wiki")
```

### Using wiki links in content

Content can reference other wiki pages using `[[Page Title]]` syntax. This syntax is resolved by the frontend when rendering the page — links are clickable if the page exists and shown with a dashed underline if it does not.

Example content:
```markdown
See [[Architecture]] for system design details.
Refer to [[Runbook]] before deploying.
```

The `GET /api/wiki/resolve?titles=Architecture,Runbook` endpoint resolves these titles to slugs for rendering.
