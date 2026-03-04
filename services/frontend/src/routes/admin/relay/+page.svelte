<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { goto } from '$app/navigation';

	let { data }: { data: { user: { is_admin: boolean } | null } } = $props();

	interface Channel {
		name: string;
		message_count: number;
		last_activity: string | null;
	}

	interface Message {
		id: string;
		content: string;
		sender: string;
		timestamp: string;
	}

	let channels = $state<Channel[]>([]);
	let messages = $state<Message[]>([]);
	let selectedChannel = $state<string | null>(null);
	let loading = $state(true);
	let error = $state('');
	let autoRefresh = $state(true);
	let refreshTimer: ReturnType<typeof setInterval> | null = null;
	let filterText = $state('');

	// Send form
	let showSendForm = $state(false);
	let sendSender = $state('admin-ui');
	let sendContent = $state('');
	let sending = $state(false);

	let msgListEl: HTMLDivElement | undefined = $state(undefined);

	function filteredMessages(): Message[] {
		if (!filterText) return messages;
		const q = filterText.toLowerCase();
		return messages.filter(
			(m) => m.content.toLowerCase().includes(q) || m.sender.toLowerCase().includes(q)
		);
	}

	async function fetchJSON(path: string, opts?: RequestInit) {
		const resp = await fetch(path, { credentials: 'include', ...opts });
		if (!resp.ok) {
			if (resp.status === 401) {
				goto('/login');
				return null;
			}
			if (resp.status === 403) {
				goto('/');
				return null;
			}
			throw new Error(`HTTP ${resp.status}`);
		}
		return resp.json();
	}

	async function loadChannels() {
		try {
			const data = await fetchJSON('/api/admin/relay/channels');
			if (!data) return;
			if (data.error) {
				error = data.error;
				channels = [];
			} else {
				error = '';
				channels = (data.channels || []).sort((a: Channel, b: Channel) =>
					(b.last_activity || '').localeCompare(a.last_activity || '')
				);
			}
		} catch (err) {
			error = (err as Error).message;
		}
	}

	async function loadMessages() {
		if (!selectedChannel) return;
		try {
			const data = await fetchJSON(
				`/api/admin/relay/channels/${encodeURIComponent(selectedChannel)}/messages?limit=200`
			);
			if (!data) return;
			messages = data.messages || [];
			await tick();
			scrollToBottom();
		} catch {
			// ignore - channels will show error
		}
	}

	function scrollToBottom() {
		if (msgListEl) {
			msgListEl.scrollTop = msgListEl.scrollHeight;
		}
	}

	function selectChannel(name: string) {
		selectedChannel = name;
		messages = [];
		filterText = '';
		showSendForm = false;
		loadMessages();
	}

	async function handleSend() {
		if (!selectedChannel || !sendContent.trim()) return;
		sending = true;
		try {
			await fetchJSON(`/api/admin/relay/channels/${encodeURIComponent(selectedChannel)}/messages`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ content: sendContent, sender: sendSender || 'admin-ui' })
			});
			sendContent = '';
			await loadMessages();
			await loadChannels();
		} catch {
			// ignore
		} finally {
			sending = false;
		}
	}

	async function handleClear() {
		if (!selectedChannel || !confirm(`Clear all messages in #${selectedChannel}?`)) return;
		try {
			await fetchJSON(`/api/admin/relay/channels/${encodeURIComponent(selectedChannel)}/clear`, {
				method: 'POST'
			});
			messages = [];
			await loadChannels();
		} catch {
			// ignore
		}
	}

	function formatTime(iso: string): string {
		try {
			return new Date(iso).toLocaleTimeString(undefined, {
				hour12: false,
				hour: '2-digit',
				minute: '2-digit',
				second: '2-digit'
			});
		} catch {
			return iso;
		}
	}

	function formatContent(content: string): { text: string; isJson: boolean } {
		try {
			const parsed = JSON.parse(content);
			return { text: JSON.stringify(parsed, null, 2), isJson: true };
		} catch {
			return { text: content, isJson: false };
		}
	}

	function startRefresh() {
		stopRefresh();
		refreshTimer = setInterval(() => {
			loadChannels();
			if (selectedChannel) loadMessages();
		}, 2000);
	}

	function stopRefresh() {
		if (refreshTimer) {
			clearInterval(refreshTimer);
			refreshTimer = null;
		}
	}

	function toggleAutoRefresh() {
		autoRefresh = !autoRefresh;
		if (autoRefresh) startRefresh();
		else stopRefresh();
	}

	function handleContentKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSend();
		}
	}

	onMount(() => {
		if (!data.user?.is_admin) {
			goto('/');
			return;
		}
		loadChannels().then(() => {
			loading = false;
		});
		startRefresh();
		return () => stopRefresh();
	});
</script>

<svelte:head>
	<title>MCP Relay - Admin</title>
</svelte:head>

<main class="relay-page">
	<!-- Sidebar -->
	<aside class="relay-sidebar">
		<div class="sidebar-header">
			<h2>Channels</h2>
			<div class="auto-refresh-toggle">
				<span class="live-dot" class:paused={!autoRefresh}></span>
				<label>
					<input type="checkbox" checked={autoRefresh} onchange={toggleAutoRefresh} />
					Live
				</label>
			</div>
		</div>
		<div class="channel-list">
			{#if loading}
				<div class="empty-state">Loading...</div>
			{:else if error}
				<div class="empty-state error-text">{error}</div>
			{:else if channels.length === 0}
				<div class="empty-state">No channels yet</div>
			{:else}
				{#each channels as ch}
					<button
						class="channel-item"
						class:active={ch.name === selectedChannel}
						onclick={() => selectChannel(ch.name)}
					>
						<span class="channel-name">#{ch.name}</span>
						<span class="channel-count">{ch.message_count}</span>
					</button>
				{/each}
			{/if}
		</div>
	</aside>

	<!-- Messages -->
	<section class="relay-main">
		<div class="msg-header">
			<h2>
				{#if selectedChannel}
					<span class="channel-label">#{selectedChannel}</span>
				{:else}
					Select a channel
				{/if}
			</h2>
			{#if selectedChannel}
				<div class="msg-actions">
					<input
						type="text"
						class="filter-input"
						placeholder="Filter messages..."
						bind:value={filterText}
					/>
					<button class="btn btn-sm btn-secondary" onclick={() => (showSendForm = !showSendForm)}>
						{showSendForm ? 'Hide' : 'Send'}
					</button>
					<button class="btn btn-sm btn-danger" onclick={handleClear}>Clear</button>
				</div>
			{/if}
		</div>

		<div class="msg-list" bind:this={msgListEl}>
			{#if !selectedChannel}
				<div class="empty-state">Select a channel to view messages</div>
			{:else if filteredMessages().length === 0}
				<div class="empty-state">
					{filterText ? 'No matching messages' : 'No messages in this channel'}
				</div>
			{:else}
				{#each filteredMessages() as msg (msg.id)}
					{@const formatted = formatContent(msg.content)}
					<div class="msg-item">
						<div class="msg-meta">
							<span class="msg-time">{formatTime(msg.timestamp)}</span>
							<span class="msg-sender">{msg.sender}</span>
							<span class="msg-id">{msg.id.slice(0, 8)}</span>
						</div>
						<pre class="msg-content" class:json={formatted.isJson}>{formatted.text}</pre>
					</div>
				{/each}
			{/if}
		</div>

		{#if showSendForm && selectedChannel}
			<div class="send-form">
				<input type="text" class="sender-input" placeholder="sender" bind:value={sendSender} />
				<textarea
					class="content-input"
					placeholder="Message content (Enter to send, Shift+Enter for newline)"
					bind:value={sendContent}
					onkeydown={handleContentKeydown}
					rows="2"
				></textarea>
				<button
					class="btn btn-sm btn-primary"
					onclick={handleSend}
					disabled={sending || !sendContent.trim()}
				>
					{sending ? 'Sending...' : 'Send'}
				</button>
			</div>
		{/if}
	</section>
</main>

<style>
	.relay-page {
		display: flex;
		height: calc(100vh - 4rem);
		overflow: hidden;
	}

	/* Sidebar */
	.relay-sidebar {
		width: 240px;
		min-width: 240px;
		border-right: 1px solid var(--border-color);
		background: var(--bg-card);
		display: flex;
		flex-direction: column;
	}

	.sidebar-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.75rem 1rem;
		border-bottom: 1px solid var(--border-color);
	}

	.sidebar-header h2 {
		font-size: 0.75rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--text-muted);
		margin: 0;
	}

	.auto-refresh-toggle {
		display: flex;
		align-items: center;
		gap: 0.375rem;
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.auto-refresh-toggle label {
		cursor: pointer;
		display: flex;
		align-items: center;
		gap: 0.25rem;
	}

	.auto-refresh-toggle input[type='checkbox'] {
		accent-color: var(--primary-500);
	}

	.live-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--success-500, #22c55e);
		display: inline-block;
		animation: pulse 2s infinite;
	}

	.live-dot.paused {
		background: var(--text-muted);
		animation: none;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.4;
		}
	}

	.channel-list {
		flex: 1;
		overflow-y: auto;
	}

	.channel-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		width: 100%;
		padding: 0.5rem 1rem;
		border: none;
		border-left: 3px solid transparent;
		background: none;
		cursor: pointer;
		font-family: inherit;
		font-size: 0.8125rem;
		color: var(--text-secondary);
		transition: background-color 0.15s;
		text-align: left;
	}

	.channel-item:hover {
		background-color: var(--bg-hover);
	}

	.channel-item.active {
		background-color: var(--bg-hover);
		border-left-color: var(--primary-500);
	}

	.channel-name {
		color: var(--primary-600);
		font-weight: 500;
	}

	.channel-count {
		font-size: 0.6875rem;
		color: var(--text-muted);
		background: var(--bg-secondary, var(--bg-hover));
		padding: 0.0625rem 0.375rem;
		border-radius: 0.5rem;
	}

	.empty-state {
		padding: 2rem 1rem;
		text-align: center;
		color: var(--text-muted);
		font-size: 0.8125rem;
	}

	.error-text {
		color: var(--error-600, #dc2626);
	}

	/* Main area */
	.relay-main {
		flex: 1;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		min-width: 0;
	}

	.msg-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 0.625rem 1rem;
		border-bottom: 1px solid var(--border-color);
		background: var(--bg-card);
		gap: 0.75rem;
		flex-wrap: wrap;
	}

	.msg-header h2 {
		font-size: 0.875rem;
		font-weight: 600;
		margin: 0;
		color: var(--text-primary);
	}

	.channel-label {
		color: var(--primary-600);
	}

	.msg-actions {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.filter-input {
		font-family: inherit;
		font-size: 0.75rem;
		padding: 0.25rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-primary);
		color: var(--text-primary);
		width: 160px;
	}

	.filter-input:focus {
		outline: none;
		border-color: var(--primary-500);
	}

	.btn-sm {
		font-size: 0.75rem;
		padding: 0.25rem 0.625rem;
	}

	.btn-danger {
		color: var(--error-600, #dc2626);
		border-color: var(--error-600, #dc2626);
		background: transparent;
	}

	.btn-danger:hover {
		background: var(--error-600, #dc2626);
		color: white;
	}

	/* Message list */
	.msg-list {
		flex: 1;
		overflow-y: auto;
		padding: 0.25rem 0;
	}

	.msg-item {
		padding: 0.375rem 1rem;
		border-bottom: 1px solid var(--border-color-light, rgba(128, 128, 128, 0.08));
	}

	.msg-item:hover {
		background-color: var(--bg-hover);
	}

	.msg-meta {
		display: flex;
		gap: 0.625rem;
		align-items: baseline;
		margin-bottom: 0.125rem;
	}

	.msg-time {
		color: var(--text-muted);
		font-size: 0.6875rem;
		font-family: var(--font-mono, monospace);
	}

	.msg-sender {
		color: var(--success-600, #16a34a);
		font-size: 0.75rem;
		font-weight: 600;
	}

	.msg-id {
		color: var(--text-muted);
		font-size: 0.625rem;
		opacity: 0.5;
		font-family: var(--font-mono, monospace);
	}

	.msg-content {
		white-space: pre-wrap;
		word-break: break-word;
		color: var(--text-primary);
		line-height: 1.5;
		font-size: 0.8125rem;
		font-family: var(--font-mono, monospace);
		margin: 0;
		background: none;
		border: none;
		padding: 0;
	}

	.msg-content.json {
		color: var(--primary-400, #818cf8);
	}

	/* Send form */
	.send-form {
		display: flex;
		align-items: flex-start;
		gap: 0.5rem;
		padding: 0.625rem 1rem;
		border-top: 1px solid var(--border-color);
		background: var(--bg-card);
	}

	.sender-input {
		font-family: inherit;
		font-size: 0.75rem;
		padding: 0.375rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-primary);
		color: var(--text-primary);
		width: 100px;
	}

	.content-input {
		flex: 1;
		font-family: var(--font-mono, monospace);
		font-size: 0.75rem;
		padding: 0.375rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-primary);
		color: var(--text-primary);
		resize: vertical;
		min-height: 2rem;
	}

	.sender-input:focus,
	.content-input:focus {
		outline: none;
		border-color: var(--primary-500);
	}

	/* Responsive */
	@media (max-width: 768px) {
		.relay-page {
			flex-direction: column;
			height: auto;
			min-height: calc(100vh - 4rem);
		}

		.relay-sidebar {
			width: 100%;
			min-width: 0;
			max-height: 200px;
			border-right: none;
			border-bottom: 1px solid var(--border-color);
		}

		.relay-main {
			flex: 1;
			min-height: 400px;
		}

		.filter-input {
			width: 100px;
		}
	}
</style>
