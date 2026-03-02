<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import { stripHtml } from '$lib/utils/markdown';
	import type { Article, ArticleRating, ApiResponse } from '$lib/types';

	let articles: Article[] = $state([]);
	let loading = $state(true);
	let showFeaturedOnly = $state(true);
	let showUnreadOnly = $state(false);
	let showBookmarkedOnly = $state(false);
	let feedTypeFilter = $state<'all' | 'paper' | 'article'>('all');
	let searchQuery = $state('');
	let total = $state(0);
	let hasMore = $state(true);
	let loadingMore = $state(false);
	let limit = 50;
	let offset = 0;

	onMount(async () => {
		await loadArticles();
	});

	async function loadArticles(reset = false) {
		try {
			if (reset) {
				offset = 0;
				articles = [];
			}

			loading = reset || offset === 0;
			loadingMore = !loading && offset > 0;

			const params: Record<string, string> = {
				limit: String(limit),
				offset: String(offset)
			};

			if (showFeaturedOnly) {
				params.featured = 'true';
			}

			if (showUnreadOnly) {
				params.unread_only = 'true';
			}

			if (showBookmarkedOnly) {
				params.bookmarked_only = 'true';
			}

			if (feedTypeFilter !== 'all') {
				params.feed_type = feedTypeFilter;
			}

			if (searchQuery.trim()) {
				params.search = searchQuery.trim();
			}

			const response = await api.get<ApiResponse<Article[]>>('/api/news', { params });

			if (response.data) {
				articles = reset ? response.data : [...articles, ...response.data];
				total = response.meta?.count || 0;
				hasMore = articles.length < total;
			}
		} catch (error) {
			toasts.show('Failed to load news: ' + (error as Error).message, 'error');
		} finally {
			loading = false;
			loadingMore = false;
		}
	}

	function handleFilterChange() {
		loadArticles(true);
	}

	async function handleSearch() {
		await loadArticles(true);
	}

	async function loadMore() {
		if (!hasMore || loadingMore) return;
		offset += limit;
		await loadArticles();
	}

	async function markAsRead(articleId: number, isRead: boolean) {
		try {
			await api.post(`/api/news/${articleId}/read`, { is_read: isRead });

			// Update local state
			articles = articles.map((a) =>
				a.id === articleId
					? { ...a, is_read: isRead, read_at: isRead ? new Date().toISOString() : null }
					: a
			);

			toasts.show(isRead ? 'Marked as read' : 'Marked as unread', 'success');
		} catch (error) {
			toasts.show('Failed to update read status: ' + (error as Error).message, 'error');
		}
	}

	async function rateArticle(articleId: number, rating: ArticleRating) {
		try {
			await api.post(`/api/news/${articleId}/rate`, { rating });

			// Update local state
			articles = articles.map((a) =>
				a.id === articleId ? { ...a, rating, rated_at: new Date().toISOString() } : a
			);

			toasts.show('Rating saved', 'success');
		} catch (error) {
			toasts.show('Failed to rate article: ' + (error as Error).message, 'error');
		}
	}

	async function toggleBookmark(articleId: number) {
		const article = articles.find((a) => a.id === articleId);
		if (!article) return;

		const newState = !article.is_bookmarked;
		articles = articles.map((a) =>
			a.id === articleId
				? {
						...a,
						is_bookmarked: newState,
						bookmarked_at: newState ? new Date().toISOString() : null
					}
				: a
		);

		try {
			await api.post(`/api/news/${articleId}/bookmark`, { is_bookmarked: newState });
			toasts.show(newState ? 'Saved for later' : 'Bookmark removed', 'success');
		} catch (error) {
			// Revert
			articles = articles.map((a) =>
				a.id === articleId
					? {
							...a,
							is_bookmarked: !newState,
							bookmarked_at: !newState ? new Date().toISOString() : null
						}
					: a
			);
			toasts.show('Failed to update bookmark: ' + (error as Error).message, 'error');
		}
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'Unknown date';
		const date = new Date(dateStr);
		const now = new Date();
		const diffMs = now.getTime() - date.getTime();
		const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

		if (diffDays === 0) return 'Today';
		if (diffDays === 1) return 'Yesterday';
		if (diffDays < 7) return `${diffDays} days ago`;
		if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
		if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;

		return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
	}
</script>

<div class="container mx-auto p-6">
	<header class="page-header">
		<h1>AI/LLM Security News</h1>
		<p>
			Stay updated with the latest security research, vulnerabilities, and best practices for AI and
			large language models.
		</p>
	</header>

	<!-- Source Toggle -->
	<div class="filter-toggle">
		<button
			class="filter-toggle-btn"
			class:active={showFeaturedOnly}
			onclick={() => {
				showFeaturedOnly = true;
				loadArticles(true);
			}}
		>
			Featured
		</button>
		<button
			class="filter-toggle-btn"
			class:active={!showFeaturedOnly}
			onclick={() => {
				showFeaturedOnly = false;
				loadArticles(true);
			}}
		>
			All Sources
		</button>
	</div>

	<!-- Filters and Search -->
	<div class="flex gap-4 mb-6 items-center flex-wrap">
		<label class="flex items-center gap-2 cursor-pointer">
			<input
				type="checkbox"
				bind:checked={showUnreadOnly}
				onchange={handleFilterChange}
				class="checkbox"
			/>
			<span>Show unread only</span>
		</label>

		<label class="flex items-center gap-2 cursor-pointer">
			<input
				type="checkbox"
				bind:checked={showBookmarkedOnly}
				onchange={handleFilterChange}
				class="checkbox"
			/>
			<span>Saved only</span>
		</label>

		<div class="flex items-center gap-2">
			<label for="feed-type-filter" class="text-sm font-medium">Type:</label>
			<select
				id="feed-type-filter"
				bind:value={feedTypeFilter}
				onchange={handleFilterChange}
				class="select select-sm"
			>
				<option value="all">All</option>
				<option value="article">Articles</option>
				<option value="paper">Papers</option>
			</select>
		</div>

		<div class="flex-1 min-w-[300px]">
			<form
				onsubmit={(e) => {
					e.preventDefault();
					handleSearch();
				}}
				class="flex gap-2"
			>
				<input
					type="text"
					bind:value={searchQuery}
					placeholder="Search articles..."
					class="input flex-1"
				/>
				<button type="submit" class="btn btn-primary">Search</button>
			</form>
		</div>

		<div class="article-count">
			{total}
			{total === 1 ? 'article' : 'articles'}
		</div>
	</div>

	<!-- Rating Legend -->
	<div class="rating-guide">
		<h3>Rating Guide:</h3>
		<ul>
			<li>
				<strong>Good:</strong> High-quality content that's relevant and useful
			</li>
			<li>
				<strong>Bad:</strong> Poor quality, misleading, or inaccurate content
			</li>
			<li>
				<strong>Not Interested:</strong> Good quality but not relevant to your interests
			</li>
		</ul>
		<p class="rating-guide-note">
			Your ratings help improve future article recommendations by adjusting source quality scores.
		</p>
	</div>

	<!-- Articles List -->
	{#if loading}
		<div class="loading-state">
			<div class="spinner"></div>
			<p>Loading articles...</p>
		</div>
	{:else if articles.length === 0}
		<div class="empty-state">
			<p>No articles found.</p>
			{#if searchQuery || showUnreadOnly || showFeaturedOnly || showBookmarkedOnly}
				<button
					onclick={() => {
						searchQuery = '';
						showUnreadOnly = false;
						showFeaturedOnly = false;
						showBookmarkedOnly = false;
						loadArticles(true);
					}}
					class="btn btn-outline mt-4"
				>
					Clear filters
				</button>
			{/if}
		</div>
	{:else}
		<div class="space-y-4">
			{#each articles as article (article.id)}
				<div class="article-card" class:article-read={article.is_read}>
					<div class="flex justify-between items-start gap-4">
						<div class="flex-1">
							<div class="flex items-center gap-2 mb-2">
								<a
									href={article.url}
									target="_blank"
									rel="noopener noreferrer"
									class="text-xl font-semibold text-blue-600 hover:text-blue-800 hover:underline"
									onclick={() => {
										if (!article.is_read) markAsRead(article.id, true);
									}}
								>
									{article.title}
								</a>
								{#if article.is_read}
									<span class="badge badge-sm bg-gray-200 text-gray-700">Read</span>
								{/if}
								{#if article.rating}
									<span
										class="badge badge-sm"
										class:bg-green-200={article.rating === 'good'}
										class:text-green-800={article.rating === 'good'}
										class:bg-red-200={article.rating === 'bad'}
										class:text-red-800={article.rating === 'bad'}
										class:bg-yellow-200={article.rating === 'not_interested'}
										class:text-yellow-800={article.rating === 'not_interested'}
									>
										{article.rating === 'not_interested' ? 'Not Interested' : article.rating}
									</span>
								{/if}
							</div>

							<div class="article-meta">
								<span class="font-medium">{article.feed_source_name}</span>
								{#if article.author}
									<span> &bull; {article.author}</span>
								{/if}
								<span> &bull; {formatDate(article.published_at)}</span>
							</div>

							{#if article.summary}
								<p class="article-summary">{stripHtml(article.summary)}</p>
							{/if}

							{#if article.keywords.length > 0}
								<div class="flex flex-wrap gap-1 mb-3">
									{#each article.keywords.slice(0, 5) as keyword}
										<span class="badge badge-sm bg-purple-100 text-purple-700">{keyword}</span>
									{/each}
								</div>
							{/if}
						</div>

						<div class="flex flex-col gap-2">
							<button
								onclick={() => toggleBookmark(article.id)}
								class="btn btn-sm"
								class:btn-primary={article.is_bookmarked}
								class:btn-outline={!article.is_bookmarked}
								title={article.is_bookmarked ? 'Remove bookmark' : 'Save for later'}
							>
								{#if article.is_bookmarked}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										viewBox="0 0 20 20"
										fill="currentColor"
										width="14"
										height="14"
										style="display: inline; vertical-align: -2px; margin-right: 4px;"
									>
										<path
											fill-rule="evenodd"
											d="M10 2c-1.716 0-3.408.106-5.07.31C3.806 2.45 3 3.414 3 4.517V17.25a.75.75 0 001.075.676L10 15.082l5.925 2.844A.75.75 0 0017 17.25V4.517c0-1.103-.806-2.068-1.93-2.207A41.403 41.403 0 0010 2z"
											clip-rule="evenodd"
										/>
									</svg>
									Saved
								{:else}
									<svg
										xmlns="http://www.w3.org/2000/svg"
										fill="none"
										viewBox="0 0 24 24"
										stroke-width="1.5"
										stroke="currentColor"
										width="14"
										height="14"
										style="display: inline; vertical-align: -2px; margin-right: 4px;"
									>
										<path
											stroke-linecap="round"
											stroke-linejoin="round"
											d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"
										/>
									</svg>
									Save
								{/if}
							</button>

							<button
								onclick={() => markAsRead(article.id, !article.is_read)}
								class="btn btn-sm btn-outline"
								title={article.is_read ? 'Mark as unread' : 'Mark as read'}
							>
								{article.is_read ? 'Unread' : 'Read'}
							</button>

							<div class="flex flex-col gap-1">
								<button
									onclick={() => rateArticle(article.id, 'good')}
									class="btn btn-sm"
									class:btn-success={article.rating === 'good'}
									class:btn-outline={article.rating !== 'good'}
									title="Good quality"
								>
									Good
								</button>
								<button
									onclick={() => rateArticle(article.id, 'bad')}
									class="btn btn-sm"
									class:btn-error={article.rating === 'bad'}
									class:btn-outline={article.rating !== 'bad'}
									title="Poor quality"
								>
									Bad
								</button>
								<button
									onclick={() => rateArticle(article.id, 'not_interested')}
									class="btn btn-sm"
									class:btn-warning={article.rating === 'not_interested'}
									class:btn-outline={article.rating !== 'not_interested'}
									title="Not relevant to your interests"
								>
									Skip
								</button>
							</div>
						</div>
					</div>
				</div>
			{/each}
		</div>

		<!-- Load More -->
		{#if hasMore}
			<div class="text-center mt-6">
				<button onclick={loadMore} class="btn btn-outline" disabled={loadingMore}>
					{loadingMore ? 'Loading...' : 'Load More'}
				</button>
			</div>
		{/if}
	{/if}
</div>

<style>
	/* Page Header */
	.page-header {
		margin-bottom: 2rem;
		padding-bottom: 1.5rem;
		border-bottom: 1px solid var(--border-color);
	}

	.page-header h1 {
		font-size: 1.875rem;
		font-weight: 700;
		color: var(--text-primary);
		margin: 0 0 0.5rem 0;
	}

	.page-header p {
		color: var(--text-secondary);
		font-size: 1rem;
		line-height: 1.5;
		margin: 0;
	}

	/* Filter Toggle */
	.filter-toggle {
		display: flex;
		gap: 0.25rem;
		margin-bottom: 1.5rem;
		background-color: var(--bg-input);
		border-radius: var(--radius-lg);
		padding: 0.25rem;
		width: fit-content;
	}

	.filter-toggle-btn {
		padding: 0.5rem 1rem;
		border-radius: var(--radius-md);
		font-size: 0.875rem;
		font-weight: 500;
		transition: all 0.15s ease;
		color: var(--text-muted);
		background: transparent;
		border: none;
		cursor: pointer;
	}

	.filter-toggle-btn.active {
		background-color: var(--bg-card);
		color: var(--text-primary);
		box-shadow: var(--shadow-sm);
	}

	/* Article count */
	.article-count {
		font-size: 0.875rem;
		color: var(--text-muted);
	}

	/* Rating Guide */
	.rating-guide {
		background-color: var(--primary-50);
		border: 1px solid var(--primary-200);
		border-radius: var(--radius-lg);
		padding: 1rem 1.25rem;
		margin-bottom: 1.5rem;
	}

	.rating-guide h3 {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0 0 0.5rem 0;
	}

	.rating-guide ul {
		list-style: none;
		padding: 0;
		margin: 0;
		font-size: 0.875rem;
		color: var(--text-secondary);
	}

	.rating-guide li {
		margin-bottom: 0.25rem;
	}

	.rating-guide-note {
		font-size: 0.75rem;
		color: var(--text-muted);
		margin: 0.5rem 0 0 0;
	}

	/* Loading State */
	.loading-state {
		text-align: center;
		padding: 3rem 0;
	}

	.loading-state p {
		color: var(--text-muted);
		margin-top: 0.5rem;
	}

	/* Empty State */
	.empty-state {
		text-align: center;
		padding: 3rem 0;
		background-color: var(--bg-page);
		border-radius: var(--radius-lg);
	}

	.empty-state p {
		color: var(--text-muted);
	}

	/* Article Meta */
	.article-meta {
		font-size: 0.875rem;
		color: var(--text-muted);
		margin-bottom: 0.5rem;
	}

	/* Article Summary */
	.article-summary {
		color: var(--text-secondary);
		margin-bottom: 0.75rem;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	/* Spinner */
	.spinner {
		width: 48px;
		height: 48px;
		border: 4px solid var(--border-color);
		border-top: 4px solid var(--primary-500);
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin: 0 auto;
	}

	@keyframes spin {
		0% {
			transform: rotate(0deg);
		}
		100% {
			transform: rotate(360deg);
		}
	}

	.line-clamp-3 {
		display: -webkit-box;
		-webkit-line-clamp: 3;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}

	/* Article card */
	.article-card {
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius-lg);
		padding: 1.25rem;
		transition:
			box-shadow 0.15s ease,
			background-color 0.15s ease;
	}

	.article-card:hover {
		box-shadow: var(--shadow-md);
	}

	.article-card.article-read {
		background-color: var(--bg-page);
		opacity: 0.75;
	}

	.badge {
		@apply px-2 py-1 rounded text-xs font-medium;
	}

	.badge-sm {
		@apply px-1.5 py-0.5 text-xs;
	}
</style>
