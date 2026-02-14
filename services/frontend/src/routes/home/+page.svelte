<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import type { Todo, Article, ApiResponse } from '$lib/types';

	let tasks: Todo[] = [];
	let overdueTasks: Todo[] = [];
	let articles: Article[] = [];
	let tasksLoading = true;
	let articlesLoading = true;
	let tasksError = false;
	let articlesError = false;

	function getGreeting(): string {
		const hour = new Date().getHours();
		if (hour < 12) return 'Good morning';
		if (hour < 17) return 'Good afternoon';
		return 'Good evening';
	}

	function getDateString(): string {
		return new Date().toLocaleDateString(undefined, {
			weekday: 'long',
			year: 'numeric',
			month: 'long',
			day: 'numeric'
		});
	}

	function todayStr(): string {
		const d = new Date();
		return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
	}

	function localMidnight(dateStr: string): Date {
		// Parse YYYY-MM-DD as local midnight (not UTC) so date comparisons
		// reflect the user's timezone. Do NOT use new Date(dateStr) or
		// append 'T00:00:00Z' — both interpret as UTC which shifts the
		// date for users west of Greenwich.
		const [y, m, d] = dateStr.split('-').map(Number);
		return new Date(y, m - 1, d);
	}

	function formatDueDate(dateStr: string | null): string {
		if (!dateStr) return '';
		const due = localMidnight(dateStr);
		const today = new Date();
		today.setHours(0, 0, 0, 0);
		const diff = Math.floor((due.getTime() - today.getTime()) / 86400000);
		if (diff < 0) return `${Math.abs(diff)}d overdue`;
		if (diff === 0) return 'today';
		if (diff === 1) return 'tomorrow';
		return due.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	function timeAgo(dateStr: string | null): string {
		if (!dateStr) return '';
		const now = new Date();
		const then = new Date(dateStr);
		const diffMs = now.getTime() - then.getTime();
		const mins = Math.floor(diffMs / 60000);
		if (mins < 1) return 'just now';
		if (mins < 60) return `${mins}m ago`;
		const hours = Math.floor(mins / 60);
		if (hours < 24) return `${hours}h ago`;
		const days = Math.floor(hours / 24);
		if (days < 7) return `${days}d ago`;
		return then.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	}

	onMount(() => {
		let mounted = true;
		const today = todayStr();

		Promise.all([
			api.get<ApiResponse<Todo[]>>('/api/todos', {
				params: { start_date: today, end_date: today }
			}),
			api.get<ApiResponse<Todo[]>>('/api/todos', { params: { status: 'overdue' } })
		])
			.then(([todayResult, overdueResult]) => {
				if (!mounted) return;
				tasks = todayResult.data || [];
				// The backend's "overdue" query can include tasks due today that
				// aren't completed yet. Since those already appear in todayResult,
				// filter them out to avoid duplicates.
				overdueTasks = (overdueResult.data || []).filter((t) => t.due_date !== today);
				tasksLoading = false;
			})
			.catch(() => {
				if (!mounted) return;
				tasksError = true;
				tasksLoading = false;
			});

		api.get<ApiResponse<Article[]>>('/api/news', {
			params: { limit: '30', unread_only: 'true' }
		})
			.then((result) => {
				if (!mounted) return;
				articles = result.data || [];
				articlesLoading = false;
			})
			.catch(() => {
				if (!mounted) return;
				articlesError = true;
				articlesLoading = false;
			});

		return () => {
			mounted = false;
		};
	});

	$: totalTasks = tasks.length + overdueTasks.length;
</script>

<svelte:head>
	<title>Home</title>
	<meta name="apple-mobile-web-app-capable" content="yes" />
	<meta name="apple-mobile-web-app-status-bar-style" content="default" />
</svelte:head>

<main class="home-container">
	<header class="home-header">
		<h1 class="greeting">{getGreeting()}</h1>
		<time class="date">{getDateString()}</time>
	</header>

	<div class="home-grid">
		<section class="panel">
			<div class="panel-header">
				<h2 class="panel-title">Due Today</h2>
				{#if !tasksLoading && !tasksError}
					<span class="badge">{totalTasks}</span>
				{/if}
			</div>

			{#if tasksLoading}
				<div class="skeleton-loader">
					<div class="skeleton-line"></div>
					<div class="skeleton-line short"></div>
					<div class="skeleton-line"></div>
				</div>
			{:else if tasksError}
				<div class="error-state">Could not load tasks</div>
			{:else if totalTasks === 0}
				<div class="empty-state">Nothing due today</div>
			{:else}
				<div class="task-list">
					{#if overdueTasks.length > 0}
						<div class="overdue-section">
							<div class="section-label overdue">Overdue</div>
							{#each overdueTasks as task}
								<a class="task-item" href="/task/{task.id}">
									<span class="priority-dot {task.priority}"></span>
									<div class="task-content">
										<div class="task-title">{task.title}</div>
										<div class="task-meta">
											<span class="task-status {task.status}"
												>{task.status.replace('_', ' ')}</span
											>
											{#if task.project_name}
												<span class="task-project">{task.project_name}</span>
											{/if}
											{#if task.due_date}
												<span>&middot;</span>
												<span>{formatDueDate(task.due_date)}</span>
											{/if}
											{#each task.tags as tag}
												<span class="task-tag">{tag}</span>
											{/each}
										</div>
									</div>
								</a>
							{/each}
						</div>
					{/if}

					{#if tasks.length > 0}
						{#if overdueTasks.length > 0}
							<div class="section-label">Today</div>
						{/if}
						{#each tasks as task}
							<a class="task-item" href="/task/{task.id}">
								<span class="priority-dot {task.priority}"></span>
								<div class="task-content">
									<div class="task-title">{task.title}</div>
									<div class="task-meta">
										<span class="task-status {task.status}"
											>{task.status.replace('_', ' ')}</span
										>
										{#if task.project_name}
											<span class="task-project">{task.project_name}</span>
										{/if}
										{#each task.tags as tag}
											<span class="task-tag">{tag}</span>
										{/each}
									</div>
								</div>
							</a>
						{/each}
					{/if}
				</div>
			{/if}
		</section>

		<section class="panel">
			<div class="panel-header">
				<h2 class="panel-title">Feed</h2>
				{#if !articlesLoading && !articlesError}
					<span class="badge">{articles.length}</span>
				{/if}
			</div>

			{#if articlesLoading}
				<div class="skeleton-loader">
					<div class="skeleton-line"></div>
					<div class="skeleton-line short"></div>
					<div class="skeleton-line"></div>
				</div>
			{:else if articlesError}
				<div class="error-state">Could not load feed</div>
			{:else if articles.length === 0}
				<div class="empty-state">No unread articles</div>
			{:else}
				<div class="article-list">
					{#each articles as article}
						<a
							class="article-item"
							class:read={article.is_read}
							href={article.url}
							target="_blank"
							rel="noopener"
						>
							<div class="article-title">{article.title}</div>
							{#if article.summary}
								<div class="article-summary">{article.summary}</div>
							{/if}
							<div class="article-meta">
								<span class="article-source">{article.feed_source_name}</span>
								<span>{timeAgo(article.published_at)}</span>
							</div>
						</a>
					{/each}
				</div>
			{/if}
		</section>
	</div>
</main>

<style>
	.home-container {
		max-width: 1280px;
		margin: 0 auto;
		padding: var(--space-8) var(--space-6);
	}

	.home-header {
		margin-bottom: var(--space-8);
	}

	.greeting {
		font-size: 1.875rem;
		font-weight: 700;
		color: var(--text-primary);
		line-height: 1.2;
	}

	.date {
		display: block;
		margin-top: var(--space-1);
		font-size: 0.875rem;
		color: var(--text-muted);
		font-weight: 500;
	}

	.home-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--space-6);
		align-items: start;
	}

	.panel {
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius-lg);
		padding: var(--space-6);
		box-shadow: var(--shadow);
	}

	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--space-4);
		padding-bottom: var(--space-3);
		border-bottom: 1px solid var(--border-color);
	}

	.panel-title {
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--text-secondary);
	}

	.badge {
		font-size: 0.75rem;
		font-weight: 500;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background: var(--gray-100);
		color: var(--text-secondary);
	}

	/* Tasks */

	.task-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.task-item {
		display: flex;
		align-items: flex-start;
		gap: var(--space-3);
		padding: 0.625rem 0.5rem;
		border-radius: var(--radius);
		transition: background var(--transition-fast);
		text-decoration: none;
		color: inherit;
	}

	.task-item:hover {
		background: var(--bg-hover);
	}

	.priority-dot {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
		margin-top: 0.375rem;
	}

	.priority-dot.urgent {
		background: var(--error-500);
	}
	.priority-dot.high {
		background: #f97316;
	}
	.priority-dot.medium {
		background: var(--warning-500);
	}
	.priority-dot.low {
		background: var(--gray-300);
	}

	.task-content {
		flex: 1;
		min-width: 0;
	}

	.task-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--text-primary);
		line-height: 1.4;
	}

	.task-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.125rem;
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.task-project {
		font-weight: 500;
		color: var(--primary-600);
	}

	.task-tag {
		padding: 0 0.375rem;
		border-radius: var(--radius);
		background: var(--gray-100);
		color: var(--text-secondary);
		font-size: 0.6875rem;
	}

	.task-status {
		display: inline-flex;
		align-items: center;
		font-size: 0.6875rem;
		font-weight: 500;
		padding: 0.125rem 0.375rem;
		border-radius: var(--radius);
		text-transform: capitalize;
	}

	.task-status.in_progress {
		background: var(--primary-50);
		color: var(--primary-600);
	}

	.task-status.pending {
		background: var(--gray-100);
		color: var(--text-muted);
	}

	.task-status.completed {
		background: var(--success-50);
		color: var(--success-500);
	}

	/* Articles */

	.article-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.article-item {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		padding: 0.625rem 0.5rem;
		border-radius: var(--radius);
		transition: background var(--transition-fast);
		text-decoration: none;
		color: inherit;
	}

	.article-item:hover {
		background: var(--bg-hover);
	}

	.article-item.read .article-title {
		color: var(--gray-400);
	}

	.article-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--text-primary);
		line-height: 1.4;
	}

	.article-summary {
		font-size: 0.8125rem;
		color: var(--text-muted);
		line-height: 1.5;
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	.article-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.75rem;
		color: var(--gray-400);
	}

	.article-source {
		font-weight: 500;
		color: var(--text-secondary);
	}

	/* Shared states */

	.empty-state {
		padding: var(--space-8) var(--space-4);
		text-align: center;
		color: var(--gray-400);
		font-size: 0.875rem;
	}

	.error-state {
		padding: var(--space-4);
		text-align: center;
		color: var(--error-500);
		font-size: 0.875rem;
		background: var(--error-50);
		border-radius: var(--radius);
	}

	.skeleton-loader {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		padding: 0.5rem;
	}

	.skeleton-line {
		height: 0.875rem;
		background: var(--gray-100);
		border-radius: var(--radius);
		animation: pulse 1.5s ease-in-out infinite;
	}

	.skeleton-line.short {
		width: 60%;
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

	.overdue-section {
		margin-bottom: var(--space-3);
		padding-bottom: var(--space-3);
		border-bottom: 1px dashed var(--border-color);
	}

	.section-label {
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		color: var(--gray-400);
		margin-bottom: var(--space-1);
	}

	.section-label.overdue {
		color: var(--error-500);
	}

	@media (max-width: 768px) {
		.home-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
