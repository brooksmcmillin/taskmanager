<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import {
		getDeadlineTypeLabel,
		getDeadlineTypeColor,
		getDeadlineTypeBgColor
	} from '$lib/utils/deadline';
	import { stripHtml } from '$lib/utils/markdown';
	import { toasts } from '$lib/stores/ui';
	import type { Todo, Article, ReadingStats, ApiResponse } from '$lib/types';

	let tasks: Todo[] = $state([]);
	let overdueTasks: Todo[] = $state([]);
	let articles: Article[] = $state([]);
	let highlight: Article | null = $state(null);
	let stats: ReadingStats | null = $state(null);
	let tasksLoading = $state(true);
	let articlesLoading = $state(true);
	let tasksError = $state(false);
	let articlesError = $state(false);
	let showFeaturedOnly = $state(true);
	let completingTasks = $state(new Set<number>());

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

	function fetchArticles(featured: boolean) {
		articlesLoading = true;
		articlesError = false;
		const params: Record<string, string> = { limit: '30', unread_only: 'true' };
		if (featured) params.featured = 'true';
		api
			.get<ApiResponse<Article[]>>('/api/news', { params })
			.then((result) => {
				articles = result.data || [];
				articlesLoading = false;
			})
			.catch(() => {
				articlesError = true;
				articlesLoading = false;
			});
	}

	function toggleFeatured(featured: boolean) {
		if (showFeaturedOnly === featured) return;
		showFeaturedOnly = featured;
		fetchArticles(featured);
	}

	async function toggleBookmark(event: MouseEvent, article: Article) {
		event.preventDefault();
		event.stopPropagation();
		const newState = !article.is_bookmarked;
		article.is_bookmarked = newState;
		articles = articles;
		try {
			await api.post(`/api/news/${article.id}/bookmark`, { is_bookmarked: newState });
		} catch {
			article.is_bookmarked = !newState;
			articles = articles;
		}
	}

	async function completeTask(event: MouseEvent, taskId: number, source: 'today' | 'overdue') {
		event.preventDefault();
		event.stopPropagation();
		if (completingTasks.has(taskId)) return;
		completingTasks.add(taskId);
		completingTasks = completingTasks;
		try {
			// Save the task before removing it (for undo)
			const removedTask =
				source === 'today'
					? tasks.find((t) => t.id === taskId)
					: overdueTasks.find((t) => t.id === taskId);

			await api.post(`/api/todos/${taskId}/complete`, {});
			if (source === 'today') {
				tasks = tasks.filter((t) => t.id !== taskId);
			} else {
				overdueTasks = overdueTasks.filter((t) => t.id !== taskId);
			}

			toasts.success('Task completed', 5000, {
				label: 'Undo',
				callback: async () => {
					try {
						await api.put(`/api/todos/${taskId}`, { status: 'pending' });
						if (removedTask) {
							const restored = { ...removedTask, status: 'pending' as const };
							if (source === 'today') {
								tasks = [...tasks, restored];
							} else {
								overdueTasks = [...overdueTasks, restored];
							}
						}
					} catch {
						toasts.error('Failed to undo completion');
					}
				}
			});
		} finally {
			completingTasks.delete(taskId);
			completingTasks = completingTasks;
		}
	}

	onMount(() => {
		let mounted = true;
		const today = todayStr();

		Promise.all([
			api.get<ApiResponse<Todo[]>>('/api/todos', {
				params: { start_date: today, end_date: today, exclude_no_calendar: 'true' }
			}),
			api.get<ApiResponse<Todo[]>>('/api/todos', {
				params: { status: 'overdue', exclude_no_calendar: 'true' }
			})
		])
			.then(([todayResult, overdueResult]) => {
				if (!mounted) return;
				tasks = todayResult.data || [];
				overdueTasks = (overdueResult.data || []).filter((t) => t.due_date !== today);
				tasksLoading = false;
			})
			.catch(() => {
				if (!mounted) return;
				tasksError = true;
				tasksLoading = false;
			});

		fetchArticles(showFeaturedOnly);

		api
			.get<{ data: ReadingStats }>('/api/news/stats')
			.then((result) => {
				if (mounted) stats = result.data || null;
			})
			.catch(() => {});

		api
			.get<{ data: Article | null }>('/api/news/highlight')
			.then((result) => {
				if (mounted) highlight = result.data || null;
			})
			.catch(() => {});

		return () => {
			mounted = false;
		};
	});

	let totalTasks = $derived(tasks.length + overdueTasks.length);
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

	{#if stats}
		<div class="stats-bar">
			<div class="stat-item">
				<span class="stat-value" class:streak-active={stats.streak_days > 0}
					>{stats.streak_days}d</span
				>
				<span class="stat-label">streak</span>
			</div>
			<div class="stat-divider"></div>
			<div class="stat-item">
				<span class="stat-value">{stats.articles_read_today}</span>
				<span class="stat-label">today</span>
			</div>
			<div class="stat-divider"></div>
			<div class="stat-item">
				<span class="stat-value">{stats.articles_read_this_week}</span>
				<span class="stat-label">this week</span>
			</div>
			<div class="stat-divider"></div>
			<div class="stat-item">
				<span class="stat-value">{stats.total_bookmarked}</span>
				<span class="stat-label">saved</span>
			</div>
		</div>
	{/if}

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
									<button
										class="complete-btn"
										class:completing={completingTasks.has(task.id)}
										onclick={(e) => completeTask(e, task.id, 'overdue')}
										title="Mark complete"
									></button>
									<span class="priority-dot {task.priority}"></span>
									<div class="task-content">
										<div class="task-title">{task.title}</div>
										<div class="task-meta">
											<span class="task-status {task.status}">{task.status.replace('_', ' ')}</span>
											{#if task.project_name}
												<span class="task-project">{task.project_name}</span>
											{/if}
											{#if task.due_date}
												<span>&middot;</span>
												<span>{formatDueDate(task.due_date)}</span>
											{/if}
											{#if task.deadline_type && task.deadline_type !== 'preferred'}
												<span
													class="deadline-type-pill"
													style="color: {getDeadlineTypeColor(
														task.deadline_type
													)}; background-color: {getDeadlineTypeBgColor(task.deadline_type)}"
												>
													{getDeadlineTypeLabel(task.deadline_type)}
												</span>
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
								<button
									class="complete-btn"
									class:completing={completingTasks.has(task.id)}
									onclick={(e) => completeTask(e, task.id, 'today')}
									title="Mark complete"
								></button>
								<span class="priority-dot {task.priority}"></span>
								<div class="task-content">
									<div class="task-title">{task.title}</div>
									<div class="task-meta">
										<span class="task-status {task.status}">{task.status.replace('_', ' ')}</span>
										{#if task.project_name}
											<span class="task-project">{task.project_name}</span>
										{/if}
										{#if task.deadline_type && task.deadline_type !== 'preferred'}
											<span
												class="deadline-type-pill"
												style="color: {getDeadlineTypeColor(
													task.deadline_type
												)}; background-color: {getDeadlineTypeBgColor(task.deadline_type)}"
											>
												{getDeadlineTypeLabel(task.deadline_type)}
											</span>
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
				<div class="panel-header-right">
					<div class="filter-toggle">
						<button
							class="filter-toggle-btn"
							class:active={showFeaturedOnly}
							onclick={() => toggleFeatured(true)}>Featured</button
						>
						<button
							class="filter-toggle-btn"
							class:active={!showFeaturedOnly}
							onclick={() => toggleFeatured(false)}>All Sources</button
						>
					</div>
					{#if !articlesLoading && !articlesError}
						<span class="badge">{articles.length}</span>
					{/if}
				</div>
			</div>

			{#if highlight}
				<div class="highlight-card">
					<div class="highlight-label">Start here</div>
					<a
						class="highlight-link"
						href={highlight.url}
						target="_blank"
						rel="noopener noreferrer"
						onclick={() => {
							if (highlight && !highlight.is_read) {
								highlight.is_read = true;
								api.post(`/api/news/${highlight.id}/read`, { is_read: true }).catch(() => {
									if (highlight) highlight.is_read = false;
								});
							}
						}}
					>
						{highlight.title}
					</a>
					<div class="highlight-meta">
						<span class="article-source">{highlight.feed_source_name}</span>
						<span>{timeAgo(highlight.published_at)}</span>
					</div>
				</div>
			{/if}

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
						<div class="article-row" class:read={article.is_read}>
							<a
								class="article-item"
								href={article.url}
								target="_blank"
								rel="noopener noreferrer"
								onclick={() => {
									if (!article.is_read) {
										article.is_read = true;
										api.post(`/api/news/${article.id}/read`, { is_read: true }).catch(() => {
											article.is_read = false;
										});
									}
								}}
							>
								<div class="article-title">{article.title}</div>
								{#if article.summary}
									<div class="article-summary">{stripHtml(article.summary)}</div>
								{/if}
								<div class="article-meta">
									<span class="article-source">{article.feed_source_name}</span>
									<span>{timeAgo(article.published_at)}</span>
								</div>
							</a>
							<button
								class="bookmark-btn"
								class:bookmarked={article.is_bookmarked}
								title={article.is_bookmarked ? 'Remove bookmark' : 'Save for later'}
								onclick={(e) => toggleBookmark(e, article)}
							>
								{#if article.is_bookmarked}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										width="16"
										height="16"
									>
										<path
											fill-rule="evenodd"
											d="M10 2c-1.716 0-3.408.106-5.07.31C3.806 2.45 3 3.414 3 4.517V17.25a.75.75 0 001.075.676L10 15.082l5.925 2.844A.75.75 0 0017 17.25V4.517c0-1.103-.806-2.068-1.93-2.207A41.403 41.403 0 0010 2z"
											clip-rule="evenodd"
										/>
									</svg>
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="1.5"
										stroke="currentColor"
										width="16"
										height="16"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
										/>
									</svg>
								{/if}
							</button>
						</div>
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
		animation: fadeIn 0.4s ease-out;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(8px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.home-header {
		margin-bottom: var(--space-4);
	}

	.greeting {
		font-size: 2rem;
		font-weight: 500;
		font-style: italic;
		color: var(--text-primary);
		line-height: 1.2;
	}

	.date {
		display: block;
		margin-top: var(--space-2);
		font-size: 0.875rem;
		color: var(--text-muted);
		font-weight: 400;
		letter-spacing: 0.02em;
	}

	/* Reading Stats Bar */

	.stats-bar {
		display: flex;
		align-items: center;
		gap: var(--space-4);
		padding: var(--space-3) var(--space-4);
		margin-bottom: var(--space-6);
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-sm);
	}

	.stat-item {
		display: flex;
		align-items: baseline;
		gap: 0.375rem;
	}

	.stat-value {
		font-size: 1.25rem;
		font-weight: 700;
		color: var(--text-primary);
		font-variant-numeric: tabular-nums;
	}

	.stat-value.streak-active {
		color: var(--warning-500);
	}

	.stat-label {
		font-size: 0.75rem;
		color: var(--text-muted);
		font-weight: 500;
	}

	.stat-divider {
		width: 1px;
		height: 1.25rem;
		background: var(--border-color);
	}

	/* Highlight Card */

	.highlight-card {
		padding: var(--space-3) var(--space-4);
		margin-bottom: var(--space-4);
		background: var(--primary-50);
		border: 1px solid var(--primary-200);
		border-radius: var(--radius);
	}

	.highlight-label {
		font-size: 0.625rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--primary-600);
		margin-bottom: 0.25rem;
	}

	.highlight-link {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--primary-700);
		text-decoration: none;
		line-height: 1.4;
	}

	.highlight-link:hover {
		text-decoration: underline;
	}

	.highlight-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.25rem;
		font-size: 0.6875rem;
		color: var(--primary-400);
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
		transition:
			box-shadow 0.2s ease,
			transform 0.2s ease;
	}

	.panel:hover {
		box-shadow: var(--shadow-md);
	}

	.panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		margin-bottom: var(--space-4);
		padding-bottom: var(--space-3);
		border-bottom: 1px solid var(--border-color);
	}

	.panel-header-right {
		display: flex;
		align-items: center;
		gap: var(--space-3);
	}

	.panel-title {
		font-size: 0.6875rem;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.1em;
		color: var(--text-muted);
	}

	.badge {
		font-size: 0.6875rem;
		font-weight: 600;
		padding: 0.125rem 0.5rem;
		border-radius: 9999px;
		background: var(--primary-50);
		color: var(--primary-600);
	}

	/* Filter Toggle */

	.filter-toggle {
		display: flex;
		gap: 0.125rem;
		background-color: var(--gray-100);
		border-radius: var(--radius-md);
		padding: 0.1875rem;
	}

	.filter-toggle-btn {
		padding: 0.25rem 0.75rem;
		border-radius: var(--radius);
		font-size: 0.6875rem;
		font-weight: 500;
		transition: all 0.2s ease;
		color: var(--text-muted);
		background: transparent;
		border: none;
		cursor: pointer;
	}

	.filter-toggle-btn.active {
		background-color: var(--bg-card);
		color: var(--primary-600);
		box-shadow: var(--shadow-sm);
		font-weight: 600;
	}

	/* Complete Button */

	.complete-btn {
		width: 32px;
		align-self: stretch;
		border-radius: var(--radius);
		border: none;
		background: transparent;
		cursor: pointer;
		flex-shrink: 0;
		padding: 0;
		position: relative;
		transition: background 0.15s ease;
	}

	.complete-btn::before {
		content: '';
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		width: 16px;
		height: 16px;
		border-radius: 50%;
		border: 1.5px solid var(--gray-300);
		transition: all 0.15s ease;
	}

	.complete-btn:hover {
		background: var(--success-50);
	}

	.complete-btn:hover::before {
		border-color: var(--success-500);
	}

	.complete-btn:hover::after {
		content: '✓';
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		font-size: 9px;
		color: var(--success-500);
		font-weight: 700;
	}

	.complete-btn.completing {
		background: var(--success-50);
		opacity: 0.6;
		pointer-events: none;
	}

	.complete-btn.completing::before {
		border-color: var(--success-500);
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
		box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15);
	}
	.priority-dot.high {
		background: #ea580c;
		box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.15);
	}
	.priority-dot.medium {
		background: var(--warning-500);
		box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.15);
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
		font-weight: 600;
		color: var(--primary-600);
		font-size: 0.6875rem;
	}

	.deadline-type-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.0625rem 0.375rem;
		font-size: 0.625rem;
		font-weight: 600;
		border-radius: 9999px;
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

	.article-row {
		display: flex;
		align-items: flex-start;
		border-radius: var(--radius);
		transition: background var(--transition-fast);
	}

	.article-row:hover {
		background: var(--bg-hover);
	}

	.article-row.read {
		opacity: 0.75;
	}

	.article-row.read .article-title {
		color: var(--gray-400);
	}

	.article-item {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		padding: 0.625rem 0.5rem;
		flex: 1;
		min-width: 0;
		text-decoration: none;
		color: inherit;
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

	/* Bookmark Button */

	.bookmark-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 32px;
		height: 32px;
		margin-top: 0.625rem;
		margin-right: 0.25rem;
		border: none;
		background: transparent;
		cursor: pointer;
		border-radius: var(--radius);
		color: var(--gray-300);
		flex-shrink: 0;
		transition: all 0.15s ease;
	}

	.bookmark-btn:hover {
		color: var(--primary-500);
		background: var(--primary-50);
	}

	.bookmark-btn.bookmarked {
		color: var(--primary-600);
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

		.stats-bar {
			flex-wrap: wrap;
			gap: var(--space-3);
		}
	}
</style>
