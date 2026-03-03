<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { stripHtml } from '$lib/utils/markdown';
	import { formatDateForInput, timeAgo } from '$lib/utils/dates';
	import { toasts } from '$lib/stores/ui';
	import HomeTaskItem from '$lib/components/HomeTaskItem.svelte';
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
	let expandedSummaries = $state(new Set<number>());
	let summarizingArticles = $state(new Set<number>());
	let completingTasks = $state(new Set<number>());

	function toggleAiSummary(articleId: number) {
		const next = new Set(expandedSummaries);
		if (next.has(articleId)) {
			next.delete(articleId);
		} else {
			next.add(articleId);
		}
		expandedSummaries = next;
	}

	async function requestSummary(articleId: number) {
		if (summarizingArticles.has(articleId)) return;
		summarizingArticles = new Set([...summarizingArticles, articleId]);
		try {
			const result = await api.post<{ data: { ai_summary: string } }>(
				`/api/news/${articleId}/summarize`,
				{}
			);
			const summary = result.data.ai_summary;
			articles = articles.map((a) => (a.id === articleId ? { ...a, ai_summary: summary } : a));
			expandedSummaries = new Set([...expandedSummaries, articleId]);
		} catch (error) {
			toasts.show('Failed to generate summary. Please try again.', 'error');
		} finally {
			const next = new Set(summarizingArticles);
			next.delete(articleId);
			summarizingArticles = next;
		}
	}

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
		} catch {
			toasts.error('Failed to complete task');
		} finally {
			completingTasks.delete(taskId);
			completingTasks = completingTasks;
		}
	}

	onMount(() => {
		let mounted = true;
		const today = formatDateForInput(new Date());

		Promise.all([
			api.get<ApiResponse<Todo[]>>('/api/todos', {
				params: {
					start_date: today,
					end_date: today,
					exclude_no_calendar: 'true',
					status: 'pending'
				}
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
								<HomeTaskItem
									{task}
									{completingTasks}
									source="overdue"
									showDueDate={true}
									oncomplete={completeTask}
								/>
							{/each}
						</div>
					{/if}

					{#if tasks.length > 0}
						{#if overdueTasks.length > 0}
							<div class="section-label">Today</div>
						{/if}
						{#each tasks as task}
							<HomeTaskItem {task} {completingTasks} source="today" oncomplete={completeTask} />
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
							<div class="article-content-col">
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
								{#if article.ai_summary}
									<button class="ai-summary-toggle" onclick={() => toggleAiSummary(article.id)}>
										<svg
											class="ai-summary-chevron"
											class:expanded={expandedSummaries.has(article.id)}
											xmlns="http://www.w3.org/2000/svg"
											viewBox="0 0 20 20"
											fill="currentColor"
											width="12"
											height="12"
										>
											<path
												fill-rule="evenodd"
												d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
												clip-rule="evenodd"
											/>
										</svg>
										AI Summary
									</button>
									{#if expandedSummaries.has(article.id)}
										<div class="ai-summary-box">
											{article.ai_summary}
										</div>
									{/if}
								{:else}
									<button
										class="ai-summary-generate"
										onclick={() => requestSummary(article.id)}
										disabled={summarizingArticles.has(article.id)}
									>
										{#if summarizingArticles.has(article.id)}
											<span class="generate-spinner"></span>
											Generating...
										{:else}
											<svg
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 20 20"
												fill="currentColor"
												width="12"
												height="12"
											>
												<path
													d="M10 2a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 2zM10 15a.75.75 0 01.75.75v1.5a.75.75 0 01-1.5 0v-1.5A.75.75 0 0110 15zM10 7a3 3 0 100 6 3 3 0 000-6zM15.657 5.404a.75.75 0 10-1.06-1.06l-1.061 1.06a.75.75 0 001.06 1.06l1.06-1.06zM6.464 14.596a.75.75 0 10-1.06-1.06l-1.06 1.06a.75.75 0 001.06 1.06l1.06-1.06zM18 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 0118 10zM5 10a.75.75 0 01-.75.75h-1.5a.75.75 0 010-1.5h1.5A.75.75 0 015 10zM14.596 15.657a.75.75 0 001.06-1.06l-1.06-1.061a.75.75 0 10-1.06 1.06l1.06 1.06zM5.404 6.464a.75.75 0 001.06-1.06l-1.06-1.06a.75.75 0 10-1.06 1.06l1.06 1.06z"
												/>
											</svg>
											Summarize
										{/if}
									</button>
								{/if}
							</div>
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

	/* Tasks */

	.task-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
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

	.article-content-col {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
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

	/* AI Summary */

	.ai-summary-toggle {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: none;
		cursor: pointer;
		font-size: 0.75rem;
		font-weight: 500;
		color: var(--primary-600);
		padding: 0.125rem 0.5rem;
	}

	.ai-summary-toggle:hover {
		color: var(--primary-700);
	}

	.ai-summary-chevron {
		transition: transform 0.15s ease;
	}

	.ai-summary-chevron.expanded {
		transform: rotate(90deg);
	}

	.ai-summary-box {
		background: var(--primary-50);
		border-left: 3px solid var(--primary-300);
		border-radius: 0 var(--radius) var(--radius) 0;
		padding: 0.5rem 0.75rem;
		margin: 0 0.5rem 0.5rem 0.5rem;
		font-size: 0.8125rem;
		line-height: 1.5;
		color: var(--text-secondary);
	}

	.ai-summary-generate {
		display: inline-flex;
		align-items: center;
		gap: 0.25rem;
		background: none;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		cursor: pointer;
		font-size: 0.6875rem;
		font-weight: 500;
		color: var(--text-muted);
		padding: 0.125rem 0.5rem;
		margin: 0 0.5rem 0.25rem 0.5rem;
		transition: all 0.15s ease;
	}

	.ai-summary-generate:hover:not(:disabled) {
		color: var(--primary-600);
		border-color: var(--primary-300);
		background: var(--primary-50);
	}

	.ai-summary-generate:disabled {
		opacity: 0.7;
		cursor: default;
	}

	.generate-spinner {
		display: inline-block;
		width: 10px;
		height: 10px;
		border: 1.5px solid var(--border-color);
		border-top-color: var(--primary-500);
		border-radius: 50%;
		animation: generate-spin 0.8s linear infinite;
	}

	@keyframes generate-spin {
		to {
			transform: rotate(360deg);
		}
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
