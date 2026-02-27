"""Debug web UI and REST API for inspecting MCP Relay messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

if TYPE_CHECKING:
    from starlette.types import ASGIApp

    from mcp_relay.server import MessageStore

MAX_SENDER_LENGTH = 128


class TokenAuthMiddleware(BaseHTTPMiddleware):
    """Require a Bearer token matching the configured debug token."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]  # noqa: ANN001
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {self.token}":
            return JSONResponse(
                {"error": "Unauthorized — set Authorization: Bearer <MCP_RELAY_DEBUG_TOKEN>"},
                status_code=401,
            )
        return await call_next(request)


async def channels_handler(request: Request) -> JSONResponse:
    """Return all channels with message counts."""
    store: MessageStore = request.app.state.store
    channels = store.list_channels()
    return JSONResponse(
        {
            "channels": [
                {
                    "name": c.name,
                    "message_count": c.message_count,
                    "last_activity": c.last_activity,
                }
                for c in channels
            ],
        }
    )


async def messages_handler(request: Request) -> JSONResponse:
    """Return messages for a specific channel."""
    store: MessageStore = request.app.state.store
    channel = request.path_params["channel"]
    since = request.query_params.get("since")
    limit_str = request.query_params.get("limit", "100")

    try:
        limit = int(limit_str)
    except ValueError:
        return JSONResponse({"error": "Invalid limit parameter"}, status_code=400)

    if limit <= 0:
        limit = 100

    try:
        messages = store.get(channel, since=since, limit=limit)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return JSONResponse(
        {
            "channel": channel,
            "messages": [m.to_dict() for m in messages],
            "count": len(messages),
        }
    )


async def send_handler(request: Request) -> JSONResponse:
    """Send a message to a channel (for debug/testing)."""
    store: MessageStore = request.app.state.store
    channel = request.path_params["channel"]

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    content = body.get("content", "")
    sender = str(body.get("sender", "debug-ui"))[:MAX_SENDER_LENGTH]

    if not content:
        return JSONResponse({"error": "content is required"}, status_code=400)

    try:
        msg = store.add(channel, content, sender)
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    return JSONResponse(msg.to_dict(), status_code=201)


async def clear_handler(request: Request) -> JSONResponse:
    """Clear all messages in a channel."""
    store: MessageStore = request.app.state.store
    channel = request.path_params["channel"]
    cleared = store.clear(channel)
    return JSONResponse({"channel": channel, "cleared": cleared})


async def index_handler(request: Request) -> HTMLResponse:
    """Serve the debug web UI."""
    return HTMLResponse(DEBUG_HTML)


def create_debug_app(store: MessageStore, token: str | None = None) -> Starlette:
    """Create the debug Starlette sub-application.

    Args:
        store: The MessageStore instance to expose.
        token: If provided, all requests must include ``Authorization: Bearer <token>``.
    """
    middleware = []
    if token:
        middleware.append(
            _middleware_entry(TokenAuthMiddleware, token=token),
        )

    app = Starlette(
        routes=[
            Route("/", index_handler),
            Route("/api/channels", channels_handler),
            Route("/api/channels/{channel}/messages", messages_handler, methods=["GET"]),
            Route("/api/channels/{channel}/messages", send_handler, methods=["POST"]),
            Route("/api/channels/{channel}/clear", clear_handler, methods=["POST"]),
        ],
        middleware=middleware,
    )
    app.state.store = store
    return app


def _middleware_entry(cls: type, **kwargs: str) -> object:
    """Build a Starlette Middleware entry without importing Middleware at module level."""
    from starlette.middleware import Middleware

    return Middleware(cls, **kwargs)


DEBUG_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MCP Relay Debug</title>
<style>
  :root {
    --bg: #1a1a2e;
    --surface: #16213e;
    --surface2: #0f3460;
    --border: #1a3a6a;
    --text: #e0e0e0;
    --text-dim: #8892a4;
    --accent: #e94560;
    --accent2: #0ea5e9;
    --green: #22c55e;
    --mono: 'SF Mono', 'Cascadia Code', 'Fira Code', Consolas, monospace;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: var(--mono);
    font-size: 13px;
    background: var(--bg);
    color: var(--text);
    height: 100vh;
    display: flex;
    flex-direction: column;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  header h1 {
    font-size: 14px;
    font-weight: 600;
    color: var(--accent);
  }
  .controls { display: flex; align-items: center; gap: 12px; }
  .controls label { color: var(--text-dim); cursor: pointer; user-select: none; }
  .controls input[type="checkbox"] { accent-color: var(--accent2); }
  .live-dot {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green);
    display: inline-block;
    animation: pulse 2s infinite;
  }
  .live-dot.paused { background: var(--text-dim); animation: none; }
  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.4; }
  }
  main {
    flex: 1;
    display: flex;
    overflow: hidden;
  }
  aside {
    width: 220px;
    min-width: 220px;
    border-right: 1px solid var(--border);
    background: var(--surface);
    display: flex;
    flex-direction: column;
  }
  aside h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-dim);
    padding: 12px 12px 8px;
  }
  .channel-list {
    flex: 1;
    overflow-y: auto;
    list-style: none;
  }
  .channel-item {
    padding: 8px 12px;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-left: 3px solid transparent;
    transition: background 0.15s;
  }
  .channel-item:hover { background: var(--surface2); }
  .channel-item.active {
    background: var(--surface2);
    border-left-color: var(--accent2);
  }
  .channel-name { color: var(--accent2); }
  .channel-count {
    font-size: 11px;
    color: var(--text-dim);
    background: var(--bg);
    padding: 1px 6px;
    border-radius: 8px;
  }
  .empty-state {
    color: var(--text-dim);
    text-align: center;
    padding: 32px 16px;
    font-size: 12px;
  }
  section.messages {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .msg-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 16px;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
  }
  .msg-header h2 {
    font-size: 13px;
    font-weight: 600;
  }
  .msg-header h2 span { color: var(--accent2); }
  .msg-actions { display: flex; gap: 8px; }
  button {
    font-family: var(--mono);
    font-size: 11px;
    padding: 4px 10px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--surface2);
    color: var(--text);
    cursor: pointer;
    transition: background 0.15s;
  }
  button:hover { background: var(--accent); border-color: var(--accent); }
  button.send-btn:hover { background: var(--accent2); border-color: var(--accent2); }
  .msg-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
  }
  .msg-item {
    padding: 6px 16px;
    border-bottom: 1px solid rgba(255,255,255,0.03);
  }
  .msg-item:hover { background: rgba(255,255,255,0.02); }
  .msg-meta {
    display: flex;
    gap: 10px;
    align-items: baseline;
    margin-bottom: 3px;
  }
  .msg-time { color: var(--text-dim); font-size: 11px; }
  .msg-sender { color: var(--green); font-size: 12px; font-weight: 600; }
  .msg-id { color: var(--text-dim); font-size: 10px; opacity: 0.5; }
  .msg-content {
    white-space: pre-wrap;
    word-break: break-word;
    color: var(--text);
    line-height: 1.5;
    font-size: 12px;
  }
  .msg-content.json {
    color: #a78bfa;
  }
  .send-form {
    padding: 10px 16px;
    background: var(--surface);
    border-top: 1px solid var(--border);
    display: none;
    gap: 8px;
  }
  .send-form.visible { display: flex; }
  .send-form input, .send-form textarea {
    font-family: var(--mono);
    font-size: 12px;
    padding: 6px 8px;
    border: 1px solid var(--border);
    border-radius: 4px;
    background: var(--bg);
    color: var(--text);
    outline: none;
  }
  .send-form input:focus, .send-form textarea:focus {
    border-color: var(--accent2);
  }
  .send-form input { width: 120px; }
  .send-form textarea { flex: 1; resize: none; min-height: 28px; }
</style>
</head>
<body>
<header>
  <h1>MCP Relay Debug</h1>
  <div class="controls">
    <span class="live-dot" id="live-dot"></span>
    <label><input type="checkbox" id="auto-refresh" checked> Auto-refresh</label>
  </div>
</header>
<main>
  <aside>
    <h2>Channels</h2>
    <ul class="channel-list" id="channel-list"></ul>
  </aside>
  <section class="messages">
    <div class="msg-header">
      <h2>Messages: <span id="current-channel">select a channel</span></h2>
      <div class="msg-actions">
        <button id="btn-send-toggle" style="display:none">Send</button>
        <button id="btn-clear" style="display:none">Clear</button>
      </div>
    </div>
    <div class="msg-list" id="msg-list">
      <div class="empty-state">Select a channel to view messages</div>
    </div>
    <div class="send-form" id="send-form">
      <input type="text" id="send-sender" placeholder="sender" value="debug-ui">
      <textarea id="send-content" placeholder="message content" rows="1"></textarea>
      <button class="send-btn" id="btn-send">Send</button>
    </div>
  </section>
</main>
<script>
(function() {
  const base = window.location.pathname.replace(/\\/+$/, '');
  let activeChannel = null;
  let refreshInterval = null;

  const $channels = document.getElementById('channel-list');
  const $msgList = document.getElementById('msg-list');
  const $currentCh = document.getElementById('current-channel');
  const $autoRefresh = document.getElementById('auto-refresh');
  const $liveDot = document.getElementById('live-dot');
  const $btnClear = document.getElementById('btn-clear');
  const $btnSendToggle = document.getElementById('btn-send-toggle');
  const $sendForm = document.getElementById('send-form');
  const $sendContent = document.getElementById('send-content');
  const $sendSender = document.getElementById('send-sender');
  const $btnSend = document.getElementById('btn-send');

  async function fetchJSON(path, opts) {
    const resp = await fetch(base + path, opts);
    return resp.json();
  }

  async function loadChannels() {
    try {
      const data = await fetchJSON('/api/channels');
      renderChannels(data.channels || []);
    } catch (e) {
      console.error('Failed to load channels:', e);
    }
  }

  function renderChannels(channels) {
    if (channels.length === 0) {
      $channels.innerHTML = '<div class="empty-state">No channels yet</div>';
      return;
    }
    channels.sort((a, b) => (b.last_activity || '').localeCompare(a.last_activity || ''));
    $channels.innerHTML = channels.map(ch =>
      '<li class="channel-item' + (ch.name === activeChannel ? ' active' : '') +
      '" data-channel="' + esc(ch.name) + '">' +
      '<span class="channel-name">#' + esc(ch.name) + '</span>' +
      '<span class="channel-count">' + ch.message_count + '</span>' +
      '</li>'
    ).join('');
  }

  async function loadMessages(channel) {
    if (!channel) return;
    try {
      const data = await fetchJSON('/api/channels/' + encodeURIComponent(channel) + '/messages');
      renderMessages(data.messages || []);
    } catch (e) {
      console.error('Failed to load messages:', e);
    }
  }

  function tryFormatJSON(s) {
    try {
      const parsed = JSON.parse(s);
      return { formatted: JSON.stringify(parsed, null, 2), isJSON: true };
    } catch {
      return { formatted: s, isJSON: false };
    }
  }

  function formatTime(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleTimeString(undefined, { hour12: false });
    } catch {
      return iso;
    }
  }

  function esc(s) {
    const d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  function renderMessages(messages) {
    if (messages.length === 0) {
      $msgList.innerHTML = '<div class="empty-state">No messages in this channel</div>';
      return;
    }
    $msgList.innerHTML = messages.map(m => {
      const { formatted, isJSON } = tryFormatJSON(m.content);
      return '<div class="msg-item">' +
        '<div class="msg-meta">' +
        '<span class="msg-time">' + esc(formatTime(m.timestamp)) + '</span>' +
        '<span class="msg-sender">' + esc(m.sender) + '</span>' +
        '<span class="msg-id">' + esc(m.id.slice(0, 8)) + '</span>' +
        '</div>' +
        '<div class="msg-content' + (isJSON ? ' json' : '') + '">' +
        esc(formatted) + '</div>' +
        '</div>';
    }).join('');
    $msgList.scrollTop = $msgList.scrollHeight;
  }

  function selectChannel(channel) {
    activeChannel = channel;
    $currentCh.textContent = '#' + channel;
    $btnClear.style.display = '';
    $btnSendToggle.style.display = '';
    loadMessages(channel);
    loadChannels();
  }

  $channels.addEventListener('click', function(e) {
    const item = e.target.closest('.channel-item');
    if (item) selectChannel(item.dataset.channel);
  });

  $btnClear.addEventListener('click', async function() {
    if (!activeChannel) return;
    await fetchJSON('/api/channels/' + encodeURIComponent(activeChannel) + '/clear',
      { method: 'POST' });
    loadMessages(activeChannel);
    loadChannels();
  });

  $btnSendToggle.addEventListener('click', function() {
    $sendForm.classList.toggle('visible');
    if ($sendForm.classList.contains('visible')) $sendContent.focus();
  });

  $btnSend.addEventListener('click', sendMessage);
  $sendContent.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  async function sendMessage() {
    if (!activeChannel || !$sendContent.value.trim()) return;
    await fetchJSON('/api/channels/' + encodeURIComponent(activeChannel) + '/messages', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: $sendContent.value,
        sender: $sendSender.value || 'debug-ui',
      }),
    });
    $sendContent.value = '';
    loadMessages(activeChannel);
    loadChannels();
  }

  function startRefresh() {
    stopRefresh();
    refreshInterval = setInterval(function() {
      loadChannels();
      if (activeChannel) loadMessages(activeChannel);
    }, 2000);
    $liveDot.classList.remove('paused');
  }

  function stopRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = null;
    $liveDot.classList.add('paused');
  }

  $autoRefresh.addEventListener('change', function() {
    if ($autoRefresh.checked) startRefresh();
    else stopRefresh();
  });

  // Initial load
  loadChannels();
  startRefresh();
})();
</script>
</body>
</html>
"""
