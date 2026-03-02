"""Tests for the MCP Relay CLI tool."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner
from starlette.testclient import TestClient

from mcp_relay.cli import cli
from mcp_relay.debug import create_debug_app
from mcp_relay.server import MessageStore

TEST_TOKEN = "test-cli-token-12345"


@pytest.fixture
def store() -> MessageStore:
    return MessageStore()


@pytest.fixture
def debug_app(store: MessageStore) -> TestClient:
    """Start a debug app and return its test client."""
    app = create_debug_app(store)
    return TestClient(app)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def base_url(debug_app: TestClient) -> str:
    """Return the base URL that the CLI should target.

    Since we can't easily point the CLI at the Starlette TestClient, we test
    CLI commands by mocking httpx calls or by using the TestClient directly
    in integration-style tests.
    """
    return debug_app.base_url


class TestCliWrite:
    """Tests for the 'write' command."""

    def test_write_with_argument(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write a message passed as a positional argument."""
        app = create_debug_app(store)
        test_client = TestClient(app)

        # Patch httpx.Client to use the test client's transport
        import httpx

        original_client_init = httpx.Client.__init__

        def patched_init(self_client, **kwargs):
            kwargs.pop("base_url", None)
            kwargs.pop("headers", None)
            kwargs.pop("timeout", None)
            original_client_init(
                self_client,
                transport=test_client._transport,
                base_url="http://testserver",
                timeout=30.0,
            )

        monkeypatch.setattr(httpx.Client, "__init__", patched_init)

        result = runner.invoke(cli, ["write", "test-channel", "hello world"])
        assert result.exit_code == 0
        assert "Sent to #test-channel" in result.output
        assert "11 bytes" in result.output

        messages, _ = store.get("test-channel")
        assert len(messages) == 1
        assert messages[0].content == "hello world"
        assert messages[0].sender == "cli"

    def test_write_with_stdin(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write a message piped via stdin."""
        app = create_debug_app(store)
        test_client = TestClient(app)

        import httpx

        original_client_init = httpx.Client.__init__

        def patched_init(self_client, **kwargs):
            kwargs.pop("base_url", None)
            kwargs.pop("headers", None)
            kwargs.pop("timeout", None)
            original_client_init(
                self_client,
                transport=test_client._transport,
                base_url="http://testserver",
                timeout=30.0,
            )

        monkeypatch.setattr(httpx.Client, "__init__", patched_init)

        result = runner.invoke(cli, ["write", "test-channel"], input="piped data\n")
        assert result.exit_code == 0
        assert "Sent to #test-channel" in result.output

        messages, _ = store.get("test-channel")
        assert len(messages) == 1
        assert messages[0].content == "piped data\n"

    def test_write_custom_sender(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write with a custom sender identity."""
        app = create_debug_app(store)
        test_client = TestClient(app)

        import httpx

        original_client_init = httpx.Client.__init__

        def patched_init(self_client, **kwargs):
            kwargs.pop("base_url", None)
            kwargs.pop("headers", None)
            kwargs.pop("timeout", None)
            original_client_init(
                self_client,
                transport=test_client._transport,
                base_url="http://testserver",
                timeout=30.0,
            )

        monkeypatch.setattr(httpx.Client, "__init__", patched_init)

        result = runner.invoke(cli, ["write", "test-channel", "--sender", "my-script", "hello"])
        assert result.exit_code == 0

        messages, _ = store.get("test-channel")
        assert messages[0].sender == "my-script"

    def test_write_empty_message_errors(self, runner: CliRunner) -> None:
        """Writing an empty message should fail."""
        result = runner.invoke(cli, ["write", "test-channel"], input="   \n")
        assert result.exit_code != 0
        assert "Empty message" in result.output


class TestCliRead:
    """Tests for the 'read' command."""

    def _patch_httpx(self, monkeypatch, store):
        app = create_debug_app(store)
        test_client = TestClient(app)
        import httpx

        original_client_init = httpx.Client.__init__

        def patched_init(self_client, **kwargs):
            kwargs.pop("base_url", None)
            kwargs.pop("headers", None)
            kwargs.pop("timeout", None)
            original_client_init(
                self_client,
                transport=test_client._transport,
                base_url="http://testserver",
                timeout=30.0,
            )

        monkeypatch.setattr(httpx.Client, "__init__", patched_init)

    def test_read_empty_channel(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        result = runner.invoke(cli, ["read", "empty-channel"])
        assert result.exit_code == 0
        assert "No messages" in result.output

    def test_read_with_messages(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test-channel", "first message", "alice")
        store.add("test-channel", "second message", "bob")

        result = runner.invoke(cli, ["read", "test-channel"])
        assert result.exit_code == 0
        assert "test-channel" in result.output
        assert "alice" in result.output
        assert "first message" in result.output
        assert "bob" in result.output
        assert "second message" in result.output

    def test_read_json_output(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test-channel", "hello", "alice")

        result = runner.invoke(cli, ["read", "test-channel", "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["channel"] == "test-channel"
        assert len(data["messages"]) == 1

    def test_read_content_only(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test-channel", "line one", "alice")
        store.add("test-channel", "line two", "bob")

        result = runner.invoke(cli, ["read", "test-channel", "-c"])
        assert result.exit_code == 0
        lines = result.output.strip().split("\n")
        assert lines == ["line one", "line two"]


class TestCliChannels:
    """Tests for the 'channels' command."""

    def _patch_httpx(self, monkeypatch, store):
        app = create_debug_app(store)
        test_client = TestClient(app)
        import httpx

        original_client_init = httpx.Client.__init__

        def patched_init(self_client, **kwargs):
            kwargs.pop("base_url", None)
            kwargs.pop("headers", None)
            kwargs.pop("timeout", None)
            original_client_init(
                self_client,
                transport=test_client._transport,
                base_url="http://testserver",
                timeout=30.0,
            )

        monkeypatch.setattr(httpx.Client, "__init__", patched_init)

    def test_no_channels(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        result = runner.invoke(cli, ["channels"])
        assert result.exit_code == 0
        assert "No channels" in result.output

    def test_list_channels(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("alpha", "msg1")
        store.add("alpha", "msg2")
        store.add("beta", "msg3")

        result = runner.invoke(cli, ["channels"])
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "beta" in result.output

    def test_channels_json_output(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test", "msg")

        result = runner.invoke(cli, ["channels", "-j"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["channels"]) == 1
        assert data["channels"][0]["name"] == "test"


class TestCliClear:
    """Tests for the 'clear' command."""

    def _patch_httpx(self, monkeypatch, store):
        app = create_debug_app(store)
        test_client = TestClient(app)
        import httpx

        original_client_init = httpx.Client.__init__

        def patched_init(self_client, **kwargs):
            kwargs.pop("base_url", None)
            kwargs.pop("headers", None)
            kwargs.pop("timeout", None)
            original_client_init(
                self_client,
                transport=test_client._transport,
                base_url="http://testserver",
                timeout=30.0,
            )

        monkeypatch.setattr(httpx.Client, "__init__", patched_init)

    def test_clear_with_confirmation(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test-channel", "msg1")
        store.add("test-channel", "msg2")

        result = runner.invoke(cli, ["clear", "test-channel"], input="y\n")
        assert result.exit_code == 0
        assert "Cleared #test-channel" in result.output

        messages, _ = store.get("test-channel")
        assert messages == []

    def test_clear_with_yes_flag(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test-channel", "msg1")

        result = runner.invoke(cli, ["clear", "test-channel", "-y"])
        assert result.exit_code == 0
        assert "Cleared #test-channel" in result.output

    def test_clear_aborted(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        store.add("test-channel", "msg1")

        result = runner.invoke(cli, ["clear", "test-channel"], input="n\n")
        assert result.exit_code != 0  # click.Abort

        # Messages should still be there
        messages, _ = store.get("test-channel")
        assert len(messages) == 1

    def test_clear_nonexistent_channel(
        self, runner: CliRunner, store: MessageStore, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._patch_httpx(monkeypatch, store)
        result = runner.invoke(cli, ["clear", "nonexistent", "-y"])
        assert result.exit_code == 0
        assert "not found or already empty" in result.output


class TestCliHelp:
    """Test that help text renders correctly."""

    def test_main_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "CLI for the MCP Relay server" in result.output
        assert "write" in result.output
        assert "read" in result.output
        assert "channels" in result.output
        assert "clear" in result.output
        assert "watch" in result.output

    def test_write_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["write", "--help"])
        assert result.exit_code == 0
        assert "Write a message to a channel" in result.output
        assert "stdin" in result.output

    def test_read_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["read", "--help"])
        assert result.exit_code == 0
        assert "Read messages from a channel" in result.output

    def test_watch_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["watch", "--help"])
        assert result.exit_code == 0
        assert "Watch a channel" in result.output
