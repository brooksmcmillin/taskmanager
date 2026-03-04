"""CLI tool for interacting with the MCP Relay debug API.

Supports piping data from stdin, e.g.:
    cat file.txt | mcp-relay-cli write my-channel
    echo '{"key": "value"}' | mcp-relay-cli write my-channel
"""

from __future__ import annotations

import json
import re
import sys
import time
from typing import Any

import click
import httpx

DEFAULT_BASE_URL = "http://localhost:8002/api"
DEFAULT_SENDER = "cli"

_CHANNEL_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _make_client(base_url: str, token: str | None) -> httpx.Client:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(base_url=base_url, headers=headers, timeout=30.0)


def _validate_channel(channel: str) -> None:
    if not _CHANNEL_RE.match(channel):
        _error(f"Invalid channel name: {channel!r} (only alphanumeric, hyphens, underscores)")


def _error(msg: str) -> None:
    click.echo(f"Error: {msg}", err=True)
    sys.exit(1)


def _handle_response(resp: httpx.Response) -> dict[str, Any]:
    if resp.status_code == 401:
        _error("Unauthorized — check your --token or MCP_RELAY_TOKEN.")
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:
            detail = resp.text
        _error(f"HTTP {resp.status_code}: {detail}")
    return resp.json()


@click.group()
@click.option(
    "--url",
    envvar="MCP_RELAY_URL",
    default=DEFAULT_BASE_URL,
    show_default=True,
    help="Base URL of the MCP Relay API.",
)
@click.option(
    "--token",
    envvar="MCP_RELAY_TOKEN",
    default=None,
    help="Bearer token (OAuth or debug). Prefer MCP_RELAY_TOKEN env var over CLI flag in shared environments.",
)
@click.pass_context
def cli(ctx: click.Context, url: str, token: str | None) -> None:
    """CLI for the MCP Relay server.

    Send and receive messages on named channels via the REST API.

    Supports piping:  cat file.txt | mcp-relay-cli write my-channel
    """
    ctx.ensure_object(dict)
    ctx.obj["url"] = url.rstrip("/")
    ctx.obj["token"] = token


@cli.command()
@click.argument("channel")
@click.argument("message", required=False)
@click.option("--sender", "-s", default=DEFAULT_SENDER, show_default=True, help="Sender identity.")
@click.pass_context
def write(ctx: click.Context, channel: str, message: str | None, sender: str) -> None:
    """Write a message to a channel.

    If MESSAGE is omitted, reads from stdin. This enables piping:

        echo "hello" | mcp-relay-cli write my-channel

        cat data.json | mcp-relay-cli write my-channel
    """
    if message is None:
        if sys.stdin.isatty():
            _error("No message provided. Pass MESSAGE as an argument or pipe data via stdin.")
        message = sys.stdin.read()

    if not message.strip():
        _error("Empty message.")

    _validate_channel(channel)
    with _make_client(ctx.obj["url"], ctx.obj["token"]) as client:
        resp = client.post(
            f"/api/channels/{channel}/messages",
            json={"content": message, "sender": sender},
        )
        data = _handle_response(resp)
    click.echo(f"Sent to #{channel} ({len(message)} bytes, id={data['id'][:8]})")


@cli.command()
@click.argument("channel")
@click.option(
    "--limit",
    "-n",
    default=50,
    show_default=True,
    type=click.IntRange(1, 1000),
    help="Max messages to return.",
)
@click.option("--since", default=None, help="Only return messages after this ISO timestamp.")
@click.option("--json-output", "-j", "json_out", is_flag=True, help="Output raw JSON.")
@click.option(
    "--content-only", "-c", is_flag=True, help="Print only message content, one per line."
)
@click.pass_context
def read(
    ctx: click.Context,
    channel: str,
    limit: int,
    since: str | None,
    json_out: bool,
    content_only: bool,
) -> None:
    """Read messages from a channel.

    By default shows a formatted view. Use -j for raw JSON or -c for content only.

    Pipe-friendly:  mcp-relay-cli read my-channel -c | grep pattern
    """
    _validate_channel(channel)
    with _make_client(ctx.obj["url"], ctx.obj["token"]) as client:
        params: dict[str, str | int] = {"limit": limit}
        if since:
            params["since"] = since
        resp = client.get(f"/api/channels/{channel}/messages", params=params)
        data = _handle_response(resp)

    messages = data.get("messages", [])

    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    if content_only:
        for msg in messages:
            click.echo(msg["content"])
        return

    if not messages:
        click.echo(f"No messages in #{channel}")
        return

    click.echo(f"#{channel} ({data.get('count', len(messages))} messages)")
    click.echo("-" * 60)
    for msg in messages:
        ts = msg.get("timestamp", "")[:19]
        sender = msg.get("sender", "?")
        content = msg.get("content", "")
        click.echo(f"[{ts}] {sender}: {content}")


@cli.command()
@click.option("--json-output", "-j", "json_out", is_flag=True, help="Output raw JSON.")
@click.pass_context
def channels(ctx: click.Context, json_out: bool) -> None:
    """List all channels."""
    with _make_client(ctx.obj["url"], ctx.obj["token"]) as client:
        resp = client.get("/api/channels")
        data = _handle_response(resp)
    channel_list = data.get("channels", [])

    if json_out:
        click.echo(json.dumps(data, indent=2))
        return

    if not channel_list:
        click.echo("No channels")
        return

    for ch in channel_list:
        name = ch["name"]
        count = ch["message_count"]
        last = ch.get("last_activity", "")
        if last:
            last = last[:19]
        click.echo(f"#{name:20s}  {count:>4d} msgs  last: {last}")


@cli.command()
@click.argument("channel")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
@click.pass_context
def clear(ctx: click.Context, channel: str, yes: bool) -> None:
    """Clear all messages in a channel."""
    _validate_channel(channel)
    if not yes:
        click.confirm(f"Clear all messages in #{channel}?", abort=True)

    with _make_client(ctx.obj["url"], ctx.obj["token"]) as client:
        resp = client.post(f"/api/channels/{channel}/clear")
        data = _handle_response(resp)

    if data.get("cleared"):
        click.echo(f"Cleared #{channel}")
    else:
        click.echo(f"Channel #{channel} not found or already empty")


@cli.command()
@click.argument("channel")
@click.option(
    "--interval",
    "-i",
    default=2,
    show_default=True,
    type=click.IntRange(min=1),
    help="Poll interval in seconds.",
)
@click.option("--content-only", "-c", is_flag=True, help="Print only message content.")
@click.pass_context
def watch(ctx: click.Context, channel: str, interval: int, content_only: bool) -> None:
    """Watch a channel for new messages (polls the debug API).

    Press Ctrl+C to stop.
    """
    _validate_channel(channel)
    with _make_client(ctx.obj["url"], ctx.obj["token"]) as client:
        since: str | None = None

        # Get current latest timestamp to only show new messages
        resp = client.get(f"/api/channels/{channel}/messages", params={"limit": 1})
        data = _handle_response(resp)
        msgs = data.get("messages", [])
        if msgs:
            since = msgs[-1].get("timestamp")

        click.echo(f"Watching #{channel} (Ctrl+C to stop)...")

        try:
            while True:
                time.sleep(interval)
                params: dict[str, str | int] = {"limit": 100}
                if since:
                    params["since"] = since
                resp = client.get(f"/api/channels/{channel}/messages", params=params)
                data = _handle_response(resp)
                new_msgs = data.get("messages", [])
                for msg in new_msgs:
                    if content_only:
                        click.echo(msg["content"])
                    else:
                        ts = msg.get("timestamp", "")[:19]
                        sender = msg.get("sender", "?")
                        click.echo(f"[{ts}] {sender}: {msg['content']}")
                    since = msg.get("timestamp")
        except KeyboardInterrupt:
            click.echo("\nStopped.")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
