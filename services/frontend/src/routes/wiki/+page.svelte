<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { wiki } from '$lib/stores/wiki';
	import { toasts } from '$lib/stores/ui';
	import type { WikiPageSummary } from '$lib/types';

	let pages: WikiPageSummary[] = $state([]);
	let loading = $state(true);
	let searchQuery = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;

	const unsubscribe = wiki.subscribe((v) => (pages = v));
	onDestroy(unsubscribe);

	onMount(async () => {
		await loadPages();
	});

	async function loadPages() {
		loading = true;
		try {
			await wiki.load(searchQuery || undefined);
		} catch (error) {
			toasts.show('Failed to load wiki pages: ' + (error as Error).message, 'error');
		} finally {
			loading = false;
		}
	}

	function handleSearchInput() {
		if (searchTimeout) clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => loadPages(), 300);
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
		return new Date(dateStr).toLocaleDateString();
	}
</script>

<svelte:head>
	<title>Wiki - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="wiki-page">
		<div class="wiki-header">
			<h1>Wiki</h1>
			<a href="/wiki/new" class="btn btn-primary">New Page</a>
		</div>

		<div class="search-bar">
			<input
				type="text"
				placeholder="Search wiki pages..."
				bind:value={searchQuery}
				oninput={handleSearchInput}
				class="search-input"
			/>
		</div>

		{#if loading}
			<div class="loading-state">Loading wiki pages...</div>
		{:else if pages.length === 0}
			<div class="empty-state">
				{#if searchQuery}
					<p>No pages match your search.</p>
				{:else}
					<p>No wiki pages yet.</p>
					<a href="/wiki/new" class="btn btn-secondary">Create your first page</a>
				{/if}
			</div>
		{:else}
			<div class="page-list">
				{#each pages as page (page.id)}
					<a href="/wiki/{page.slug}" class="page-item">
						<div class="page-title">{page.title}</div>
						<div class="page-meta">
							{#if page.updated_at}
								Updated {formatDate(page.updated_at)}
							{:else}
								Created {formatDate(page.created_at)}
							{/if}
						</div>
					</a>
				{/each}
			</div>
		{/if}
	</div>
</main>

<style>
	.wiki-page {
		max-width: 800px;
		margin: 0 auto;
	}

	.wiki-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.wiki-header h1 {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0;
	}

	.search-bar {
		margin-bottom: 1.5rem;
	}

	.search-input {
		width: 100%;
		padding: 0.625rem 0.875rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-input);
		color: var(--text-primary);
		font-size: 0.875rem;
	}

	.search-input:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 3px var(--primary-100);
	}

	.loading-state,
	.empty-state {
		text-align: center;
		padding: 4rem 2rem;
		color: var(--text-secondary);
	}

	.empty-state p {
		margin-bottom: 1rem;
	}

	.page-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.page-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.875rem 1rem;
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		text-decoration: none;
		transition: all var(--transition-fast);
	}

	.page-item:hover {
		border-color: var(--primary-300);
		background: var(--bg-hover);
	}

	.page-title {
		font-size: 0.9375rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.page-meta {
		font-size: 0.75rem;
		color: var(--text-muted);
		white-space: nowrap;
		margin-left: 1rem;
	}
</style>
