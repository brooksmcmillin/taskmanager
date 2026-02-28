<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { snippets } from '$lib/stores/snippets';
	import { toasts } from '$lib/stores/ui';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import type { SnippetSummary, CategoryCount } from '$lib/types';

	let items: SnippetSummary[] = $state([]);
	let categories: CategoryCount[] = $state([]);
	let loading = $state(true);
	let searchQuery = $state('');
	let activeCategory = $state('');
	let activeTag = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let allTags: string[] = $state([]);

	const unsubscribe = snippets.subscribe((v) => (items = v));
	onDestroy(unsubscribe);

	onMount(async () => {
		const catParam = $page.url.searchParams.get('category');
		const tagParam = $page.url.searchParams.get('tag');
		if (catParam) activeCategory = catParam;
		if (tagParam) activeTag = tagParam;
		await loadSnippets();
		await loadCategories();
	});

	async function loadSnippets() {
		loading = true;
		try {
			await snippets.load({
				q: searchQuery || undefined,
				category: activeCategory || undefined,
				tag: activeTag || undefined
			});
			allTags = [...new Set(items.flatMap((s) => s.tags || []))].sort();
		} catch (error) {
			toasts.show('Failed to load snippets: ' + (error as Error).message, 'error');
		} finally {
			loading = false;
		}
	}

	async function loadCategories() {
		try {
			categories = await snippets.getCategories();
		} catch {
			// Non-critical, categories bar just won't show
		}
	}

	function handleSearchInput() {
		if (searchTimeout) clearTimeout(searchTimeout);
		searchTimeout = setTimeout(() => loadSnippets(), 300);
	}

	function selectCategory(cat: string) {
		if (activeCategory === cat) {
			activeCategory = '';
			goto('/snippets', { replaceState: true });
		} else {
			activeCategory = cat;
			goto(`/snippets?category=${encodeURIComponent(cat)}`, { replaceState: true });
		}
		loadSnippets();
	}

	function selectTag(tag: string) {
		if (activeTag === tag) {
			activeTag = '';
		} else {
			activeTag = tag;
		}
		loadSnippets();
	}

	function clearFilters() {
		activeCategory = '';
		activeTag = '';
		searchQuery = '';
		goto('/snippets', { replaceState: true });
		loadSnippets();
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
		// Parse YYYY-MM-DD as local date to avoid timezone shifts
		const parts = dateStr.split('-');
		if (parts.length === 3) {
			const d = new Date(
				parseInt(parts[0], 10),
				parseInt(parts[1], 10) - 1,
				parseInt(parts[2], 10)
			);
			return d.toLocaleDateString();
		}
		return new Date(dateStr).toLocaleDateString();
	}

	let hasActiveFilters = $derived(!!searchQuery || !!activeCategory || !!activeTag);
</script>

<svelte:head>
	<title>Snippets - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="snippets-page">
		<div class="snippets-header">
			<h1>Snippets</h1>
			<a href="/snippets/new" class="btn btn-primary">New Snippet</a>
		</div>

		<div class="search-bar">
			<input
				type="text"
				placeholder="Search snippets..."
				bind:value={searchQuery}
				oninput={handleSearchInput}
				class="search-input"
			/>
		</div>

		{#if categories.length > 0}
			<div class="category-chips">
				{#each categories as cat}
					<button
						class="category-chip"
						class:active={activeCategory === cat.category}
						onclick={() => selectCategory(cat.category)}
					>
						{cat.category}
						<span class="chip-count">{cat.count}</span>
					</button>
				{/each}
			</div>
		{/if}

		{#if allTags.length > 0}
			<div class="tag-chips">
				{#each allTags as tag}
					<button class="tag-chip" class:active={activeTag === tag} onclick={() => selectTag(tag)}>
						{tag}
					</button>
				{/each}
			</div>
		{/if}

		{#if hasActiveFilters}
			<button class="clear-filters" onclick={clearFilters}>Clear all filters</button>
		{/if}

		{#if loading}
			<div class="loading-state">Loading snippets...</div>
		{:else if items.length === 0}
			<div class="empty-state">
				{#if hasActiveFilters}
					<p>No snippets match your filters.</p>
				{:else}
					<p>No snippets yet.</p>
					<a href="/snippets/new" class="btn btn-secondary">Create your first snippet</a>
				{/if}
			</div>
		{:else}
			<div class="snippet-list">
				{#each items as s (s.id)}
					<a href="/snippets/{s.id}" class="snippet-item">
						<div class="snippet-info">
							<div class="snippet-category">{s.category}</div>
							<div class="snippet-title">{s.title}</div>
							{#if s.tags && s.tags.length > 0}
								<div class="snippet-tags">
									{#each s.tags as tag}
										<span class="tag-pill">{tag}</span>
									{/each}
								</div>
							{/if}
						</div>
						<div class="snippet-date">{formatDate(s.snippet_date)}</div>
					</a>
				{/each}
			</div>
		{/if}
	</div>
</main>

<style>
	.snippets-page {
		max-width: 800px;
		margin: 0 auto;
	}

	.snippets-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1.5rem;
	}

	.snippets-header h1 {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0;
	}

	.search-bar {
		margin-bottom: 1rem;
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

	.category-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
		margin-bottom: 0.75rem;
	}

	.category-chip {
		font-size: 0.75rem;
		padding: 0.25rem 0.625rem;
		border-radius: var(--radius);
		border: 1px solid var(--border-color);
		background: var(--bg-card);
		color: var(--text-secondary);
		cursor: pointer;
		transition: all var(--transition-fast);
		display: flex;
		align-items: center;
		gap: 0.375rem;
	}

	.category-chip:hover {
		border-color: var(--primary-400);
		color: var(--primary-600);
	}

	.category-chip.active {
		background: var(--primary-100);
		border-color: var(--primary-400);
		color: var(--primary-700);
		font-weight: 500;
	}

	.chip-count {
		font-size: 0.625rem;
		padding: 0 0.375rem;
		border-radius: 9999px;
		background: var(--bg-hover);
		color: var(--text-muted);
	}

	.category-chip.active .chip-count {
		background: var(--primary-200);
		color: var(--primary-700);
	}

	.tag-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
		margin-bottom: 0.75rem;
	}

	.tag-chip {
		font-size: 0.75rem;
		padding: 0.25rem 0.625rem;
		border-radius: 9999px;
		border: 1px solid var(--border-color);
		background: var(--bg-card);
		color: var(--text-secondary);
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.tag-chip:hover {
		border-color: var(--primary-400);
		color: var(--primary-600);
	}

	.tag-chip.active {
		background: var(--primary-100);
		border-color: var(--primary-400);
		color: var(--primary-700);
		font-weight: 500;
	}

	.clear-filters {
		font-size: 0.75rem;
		color: var(--text-muted);
		background: none;
		border: 1px dashed var(--border-color);
		padding: 0.25rem 0.625rem;
		border-radius: var(--radius);
		cursor: pointer;
		margin-bottom: 1rem;
	}

	.clear-filters:hover {
		color: var(--text-primary);
		border-color: var(--text-muted);
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

	.snippet-list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.snippet-item {
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

	.snippet-item:hover {
		border-color: var(--primary-300);
		background: var(--bg-hover);
	}

	.snippet-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
		flex-wrap: wrap;
	}

	.snippet-category {
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--primary-600);
		background: var(--primary-50);
		padding: 0.125rem 0.5rem;
		border-radius: var(--radius);
		white-space: nowrap;
	}

	.snippet-title {
		font-size: 0.9375rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.snippet-tags {
		display: flex;
		gap: 0.25rem;
	}

	.tag-pill {
		font-size: 0.625rem;
		padding: 0.0625rem 0.375rem;
		border-radius: 9999px;
		background: var(--primary-100);
		color: var(--primary-700);
		white-space: nowrap;
	}

	.snippet-date {
		font-size: 0.8125rem;
		color: var(--text-muted);
		white-space: nowrap;
		margin-left: 1rem;
		font-variant-numeric: tabular-nums;
	}
</style>
