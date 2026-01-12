#!/usr/bin/env python3
"""
Test script for TaskManager SDK

This script demonstrates the main functionality of the TaskManager SDK,
including authentication, project management, todo management, and OAuth.

Setup:
1. Create a .env file in the same directory with:
   TASKMANAGER_URL=http://localhost:4321/api
   TASKMANAGER_USERNAME=your_username
   TASKMANAGER_PASSWORD=your_password

2. Install dependencies:
   uv add python-dotenv typer

3. Run the script:
   uv run test_script.py [command]
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import typer
from dotenv import load_dotenv

from taskmanager_sdk import TaskManagerClient, create_authenticated_client
from taskmanager_sdk.exceptions import TaskManagerError

load_dotenv()

app = typer.Typer(help="TaskManager SDK Test Script")

# Configuration from environment
BASE_URL = os.getenv("TASKMANAGER_URL", "http://localhost:4321") + "/api"
USERNAME = os.getenv("TASKMANAGER_USERNAME")
PASSWORD = os.getenv("TASKMANAGER_PASSWORD")


def get_client() -> TaskManagerClient:
    """Create and return authenticated client."""
    if not USERNAME or not PASSWORD:
        typer.echo(
            "ERROR: TASKMANAGER_USERNAME and TASKMANAGER_PASSWORD must be set in .env file",
            err=True,
        )
        raise typer.Exit(1)

    try:
        client = create_authenticated_client(USERNAME, PASSWORD, BASE_URL)
        typer.echo(f"✅ Successfully authenticated as {USERNAME}")
        return client
    except TaskManagerError as e:
        typer.echo(f"❌ Authentication failed: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def auth_test():
    """Test authentication methods."""
    typer.echo("🔐 Testing Authentication...")

    if not USERNAME or not PASSWORD:
        typer.echo(
            "ERROR: TASKMANAGER_USERNAME and TASKMANAGER_PASSWORD must be set in .env file",
            err=True,
        )
        raise typer.Exit(1)

    try:
        # Test manual authentication
        client = TaskManagerClient(BASE_URL)
        response = client.login(USERNAME, PASSWORD)

        if response.success:
            typer.echo("✅ Manual login successful")

            # Test logout
            logout_response = client.logout()
            if logout_response.success:
                typer.echo("✅ Logout successful")
            else:
                typer.echo(f"❌ Logout failed: {logout_response.error}")
        else:
            typer.echo(f"❌ Manual login failed: {response.error}")

        # Test convenience function
        create_authenticated_client(USERNAME, PASSWORD, BASE_URL)
        typer.echo("✅ Convenience authentication successful")

    except TaskManagerError as e:
        typer.echo(f"❌ Authentication test failed: {e}")


@app.command()
def projects():
    """Test project management endpoints."""
    typer.echo("📁 Testing Project Management...")

    client = get_client()

    try:
        # Get existing projects
        response = client.get_projects()
        if response.success:
            projects_list = response.data or []
            typer.echo(f"✅ Found {len(projects_list)} existing projects")
            for project in projects_list:
                typer.echo(
                    f"  - {project['name']} (ID: {project['id']}, Color: {project['color']})"
                )

        # Create a test project
        test_project_name = f"Test Project {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        response = client.create_project(
            name=test_project_name,
            color="#FF5733",
            description="Test project created by SDK test script",
        )

        if response.success and response.data:
            project_id = response.data["id"]
            typer.echo(f"✅ Created project '{test_project_name}' (ID: {project_id})")

            # Update the project
            response = client.update_project(
                project_id, name=f"{test_project_name} (Updated)", color="#33FF57"
            )
            if response.success:
                typer.echo("✅ Updated project successfully")

            # Get specific project
            response = client.get_project(project_id)
            if response.success and response.data:
                typer.echo(f"✅ Retrieved project: {response.data['name']}")

            # Clean up - delete the test project
            response = client.delete_project(project_id)
            if response.success:
                typer.echo("✅ Deleted test project")
            else:
                typer.echo(f"❌ Failed to delete project: {response.error}")
        else:
            typer.echo(f"❌ Failed to create project: {response.error}")

    except TaskManagerError as e:
        typer.echo(f"❌ Project test failed: {e}")


@app.command()
def todos(project_id: Optional[int] = None):
    """Test todo management endpoints."""
    typer.echo("✅ Testing Todo Management...")

    client = get_client()

    try:
        # Get existing todos
        response = client.get_todos()
        if response.success:
            todos_list = response.data or []
            typer.echo(f"✅ Found {len(todos_list)} existing todos")
            for todo in todos_list[:3]:  # Show first 3
                status_emoji = {
                    "pending": "⏳",
                    "in_progress": "🔄",
                    "completed": "✅",
                    "cancelled": "❌",
                }.get(todo["status"], "❓")
                typer.echo(
                    f"  {status_emoji} {todo['title']} (ID: {todo['id']}, Priority: {todo['priority']})"
                )

        return

        # Create a test todo
        test_todo_title = f"Test Todo {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        due_date = (datetime.now() + timedelta(days=7)).isoformat()

        response = client.create_todo(
            title=test_todo_title,
            project_id=project_id,
            description="Test todo created by SDK test script",
            priority="high",
            estimated_hours=2.5,
            due_date=due_date,
            tags=["test", "sdk"],
        )

        if response.success:
            todo_id = response.data["id"]
            typer.echo(f"✅ Created todo '{test_todo_title}' (ID: {todo_id})")

            # Update the todo
            response = client.update_todo(
                todo_id,
                title=f"{test_todo_title} (Updated)",
                status="in_progress",
                actual_hours=1.0,
            )
            if response.success:
                typer.echo("✅ Updated todo successfully")

            # Get specific todo
            response = client.get_todo(todo_id)
            if response.success:
                typer.echo(f"✅ Retrieved todo: {response.data['title']}")

            # Complete the todo
            response = client.complete_todo(todo_id, actual_hours=2.0)
            if response.success:
                typer.echo("✅ Completed todo successfully")

            # Clean up - delete the test todo
            response = client.delete_todo(todo_id)
            if response.success:
                typer.echo("✅ Deleted test todo")
            else:
                typer.echo(f"❌ Failed to delete todo: {response.error}")
        else:
            typer.echo(f"❌ Failed to create todo: {response.error}")

    except TaskManagerError as e:
        typer.echo(f"❌ Todo test failed: {e}")


@app.command()
def oauth():
    """Test OAuth endpoints."""
    typer.echo("🔐 Testing OAuth Management...")

    client = get_client()

    try:
        # Get existing OAuth clients
        response = client.get_oauth_clients()
        if response.success:
            clients_list = response.data or []
            typer.echo(f"✅ Found {len(clients_list)} existing OAuth clients")
            for oauth_client in clients_list:
                typer.echo(
                    f"  - {oauth_client['name']} (ID: {oauth_client['client_id']}, Active: {oauth_client['is_active']})"
                )

        # Create a test OAuth client
        test_client_name = (
            f"Test OAuth Client {datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        response = client.create_oauth_client(
            name=test_client_name,
            redirect_uris=[
                "http://localhost:3000/callback",
                "https://example.com/callback",
            ],
            grant_types=["authorization_code", "refresh_token"],
            scopes=["read", "write"],
        )

        if response.success and response.data:
            typer.echo(f"✅ Created OAuth client '{test_client_name}'")
            client_data = response.data
            typer.echo(f"  Client ID: {client_data['client_id']}")
            typer.echo(f"  Client Secret: {client_data['client_secret']}")
        else:
            typer.echo(f"❌ Failed to create OAuth client: {response.error}")

        # Get JWKS
        response = client.get_jwks()
        if response.success and response.data:
            jwks_data = response.data
            typer.echo(f"✅ Retrieved JWKS with {len(jwks_data.get('keys', []))} keys")
        else:
            typer.echo(f"❌ Failed to retrieve JWKS: {response.error}")

    except TaskManagerError as e:
        typer.echo(f"❌ OAuth test failed: {e}")


@app.command()
def full_test():
    """Run all tests in sequence."""
    typer.echo("🚀 Running Full Test Suite...\n")

    auth_test()
    typer.echo()

    projects()
    typer.echo()

    todos()
    typer.echo()

    oauth()
    typer.echo()

    typer.echo("✅ Full test suite completed!")


@app.command()
def interactive():
    """Interactive mode for testing specific endpoints."""
    typer.echo("🎮 Interactive Mode - TaskManager SDK")
    typer.echo("Available commands: auth, projects, todos, oauth, quit")

    client = get_client()

    while True:
        command = typer.prompt("\nEnter command").lower().strip()

        if command == "quit":
            break
        elif command == "auth":
            auth_test()
        elif command == "projects":
            if client:
                projects()
            else:
                typer.echo("❌ No authenticated client available")
        elif command == "todos":
            if client:
                project_id = typer.prompt(
                    "Enter project ID (or press Enter for none)",
                    default="",
                    show_default=False,
                )
                todos(int(project_id) if project_id else None)
            else:
                typer.echo("❌ No authenticated client available")
        elif command == "oauth":
            if client:
                oauth()
            else:
                typer.echo("❌ No authenticated client available")
        else:
            typer.echo("Unknown command. Available: auth, projects, todos, oauth, quit")


if __name__ == "__main__":
    app()
