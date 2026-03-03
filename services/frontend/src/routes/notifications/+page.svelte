<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { notifications } from '$lib/stores/notifications';
	import { toasts } from '$lib/stores/ui';
	import type { NotificationItem } from '$lib/types';

	let items: NotificationItem[] = $state([]);
	let loading = $state(true);
	let filter: 'all' | 'unread' = $state('all');

	const unsubscribe = notifications.subscribe((v) => (items = v));

	onMount(() => {
		loadNotifications();
		return unsubscribe;
	});

	async function loadNotifications() {
		loading = true;
		try {
			await notifications.load(filter === 'unread');
		} catch {
			toasts.error('Failed to load notifications');
		} finally {
			loading = false;
		}
	}

	let prevFilter: 'all' | 'unread' = filter;
	$effect(() => {
		const currentFilter = filter;
		if (currentFilter !== prevFilter) {
			prevFilter = currentFilter;
			loadNotifications();
		}
	});

	async function handleMarkRead(item: NotificationItem) {
		if (item.is_read) return;
		try {
			await notifications.markRead(item.id);
		} catch {
			toasts.error('Failed to mark as read');
		}
	}

	async function handleMarkAllRead() {
		try {
			await notifications.markAllRead();
			toasts.success('All notifications marked as read');
		} catch {
			toasts.error('Failed to mark all as read');
		}
	}

	async function handleDelete(id: number) {
		try {
			await notifications.remove(id);
		} catch {
			toasts.error('Failed to delete notification');
		}
	}

	function handleClick(item: NotificationItem) {
		handleMarkRead(item);
		if (item.wiki_page_id) {
			goto(`/wiki/${item.wiki_page_id}`);
		}
	}

	function formatDate(dateStr: string): string {
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffMin = Math.floor(diffMs / 60000);
		const diffHr = Math.floor(diffMs / 3600000);
		const diffDay = Math.floor(diffMs / 86400000);

		if (diffMin < 1) return 'just now';
		if (diffMin < 60) return `${diffMin}m ago`;
		if (diffHr < 24) return `${diffHr}h ago`;
		if (diffDay < 7) return `${diffDay}d ago`;
		return date.toLocaleDateString();
	}

	function typeIcon(type: string): string {
		switch (type) {
			case 'wiki_page_updated':
				return 'pencil';
			case 'wiki_page_created':
				return 'plus';
			case 'wiki_page_deleted':
				return 'trash';
			default:
				return 'bell';
		}
	}
</script>

<svelte:head>
	<title>Notifications - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="notifications-page">
		<div class="page-header">
			<h1>Notifications</h1>
			<div class="header-actions">
				<button class="btn btn-secondary btn-med" onclick={handleMarkAllRead}>
					Mark all read
				</button>
			</div>
		</div>

		<div class="filter-bar">
			<button class="filter-btn" class:active={filter === 'all'} onclick={() => (filter = 'all')}>
				All
			</button>
			<button
				class="filter-btn"
				class:active={filter === 'unread'}
				onclick={() => (filter = 'unread')}
			>
				Unread
			</button>
		</div>

		{#if loading}
			<div class="loading-state">Loading notifications...</div>
		{:else if items.length === 0}
			<div class="empty-state">
				<p>No {filter === 'unread' ? 'unread ' : ''}notifications</p>
				<p class="text-muted">Subscribe to wiki pages to get notified when they are updated.</p>
			</div>
		{:else}
			<div class="notification-list">
				{#each items as item (item.id)}
					<div
						class="notification-item"
						class:unread={!item.is_read}
						role="button"
						tabindex="0"
						onclick={() => handleClick(item)}
						onkeydown={(e) => e.key === 'Enter' && handleClick(item)}
					>
						<div class="notification-icon {typeIcon(item.notification_type)}">
							{#if item.notification_type === 'wiki_page_updated'}
								<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
									<path
										d="M12.146.854a.5.5 0 0 1 .708 0l2.292 2.292a.5.5 0 0 1 0 .708l-9.5 9.5a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168l9.5-9.5z"
									/>
								</svg>
							{:else if item.notification_type === 'wiki_page_created'}
								<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
									<path
										d="M8 4a.5.5 0 0 1 .5.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3A.5.5 0 0 1 8 4z"
									/>
								</svg>
							{:else if item.notification_type === 'wiki_page_deleted'}
								<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
									<path
										d="M5.5 5.5A.5.5 0 0 1 6 6v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm2.5 0a.5.5 0 0 1 .5.5v6a.5.5 0 0 1-1 0V6a.5.5 0 0 1 .5-.5zm3 .5a.5.5 0 0 0-1 0v6a.5.5 0 0 0 1 0V6z"
									/>
									<path
										fill-rule="evenodd"
										d="M14.5 3a1 1 0 0 1-1 1H13v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4h-.5a1 1 0 0 1-1-1V2a1 1 0 0 1 1-1H6a1 1 0 0 1 1-1h2a1 1 0 0 1 1 1h3.5a1 1 0 0 1 1 1v1z"
									/>
								</svg>
							{:else}
								<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
									<path
										d="M8 16a2 2 0 0 0 2-2H6a2 2 0 0 0 2 2zm.995-14.901a1 1 0 1 0-1.99 0A5.002 5.002 0 0 0 3 6c0 1.098-.5 6-2 7h14c-1.5-1-2-5.902-2-7 0-2.42-1.72-4.44-4.005-4.901z"
									/>
								</svg>
							{/if}
						</div>
						<div class="notification-content">
							<div class="notification-title">{item.title}</div>
							<div class="notification-message">{item.message}</div>
							<div class="notification-time">{formatDate(item.created_at)}</div>
						</div>
						<button
							class="notification-dismiss"
							title="Delete notification"
							onclick={(e: MouseEvent) => {
								e.stopPropagation();
								handleDelete(item.id);
							}}
						>
							&times;
						</button>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</main>

<style>
	.notifications-page {
		max-width: 700px;
		margin: 0 auto;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.page-header h1 {
		font-size: 1.5rem;
		font-weight: 700;
		margin: 0;
		color: var(--text-primary);
	}

	.filter-bar {
		display: flex;
		gap: 0.5rem;
		margin-bottom: 1.5rem;
	}

	.filter-btn {
		padding: 0.375rem 0.875rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-card);
		color: var(--text-secondary);
		font-size: 0.875rem;
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.filter-btn:hover {
		background: var(--bg-hover);
	}

	.filter-btn.active {
		background: var(--primary-100);
		color: var(--primary-700);
		border-color: var(--primary-300);
	}

	.loading-state,
	.empty-state {
		text-align: center;
		padding: 4rem 2rem;
		color: var(--text-secondary);
	}

	.empty-state .text-muted {
		font-size: 0.875rem;
		color: var(--text-muted);
		margin-top: 0.5rem;
	}

	.notification-list {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.notification-item {
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.875rem 1rem;
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.notification-item:hover {
		background: var(--bg-hover);
		border-color: var(--primary-300);
	}

	.notification-item.unread {
		border-left: 3px solid var(--primary-600);
		background: var(--primary-50, #fff7ed);
	}

	.notification-icon {
		flex-shrink: 0;
		width: 2rem;
		height: 2rem;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		background: var(--bg-hover);
		color: var(--text-secondary);
	}

	.notification-content {
		flex: 1;
		min-width: 0;
	}

	.notification-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text-primary);
		margin-bottom: 0.125rem;
	}

	.notification-message {
		font-size: 0.8125rem;
		color: var(--text-secondary);
		margin-bottom: 0.25rem;
	}

	.notification-time {
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.notification-dismiss {
		flex-shrink: 0;
		background: none;
		border: none;
		font-size: 1.25rem;
		color: var(--text-muted);
		cursor: pointer;
		padding: 0.25rem;
		line-height: 1;
		border-radius: var(--radius-sm, 3px);
		transition: all var(--transition-fast);
	}

	.notification-dismiss:hover {
		color: var(--error-600, #dc2626);
		background: var(--bg-hover);
	}

	@media (max-width: 640px) {
		.page-header {
			flex-direction: column;
			align-items: flex-start;
			gap: 0.75rem;
		}
	}
</style>
