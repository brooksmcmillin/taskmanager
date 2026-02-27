<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { wiki } from '$lib/stores/wiki';
	import { toasts } from '$lib/stores/ui';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import WikiTreeView from '$lib/components/WikiTreeView.svelte';
	import type { WikiPageSummary, WikiTreeNode } from '$lib/types';

	let pages: WikiPageSummary[] = $state([]);
	let treeNodes: WikiTreeNode[] = $state([]);
	let loading = $state(true);
	let searchQuery = $state('');
	let activeTag = $state('');
	let searchTimeout: ReturnType<typeof setTimeout> | null = null;
	let allTags: string[] = $state([]);

	// Flat view is used when searching or filtering by tag
	let showFlat = $derived(!!searchQuery || !!activeTag);

	const unsubscribe = wiki.subscribe((v) => (pages = v));
	onDestroy(unsubscribe);

	onMount(async () => {
		// Check for tag query param
		const tagParam = $page.url.searchParams.get('tag');
		if (tagParam) {
			activeTag = tagParam;
		}
		await loadPages();
	});

	async function loadPages() {
		loading = true;
		try {
			if (searchQuery || activeTag) {
				await wiki.load(searchQuery || undefined, activeTag || undefined);
			} else {
				// Load tree for default view
				treeNodes = await wiki.loadTree();
				// Also load flat list for tag extraction
				await wiki.load();
			}
			// Derive all tags from flat list
			allTags = [...new Set(pages.flatMap((p) => p.tags || []))].sort();
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

	function selectTag(tag: string) {
		if (activeTag === tag) {
			activeTag = '';
			goto('/wiki', { replaceState: true });
		} else {
			activeTag = tag;
			goto(`/wiki?tag=${encodeURIComponent(tag)}`, { replaceState: true });
		}
		loadPages();
	}

	function clearTag() {
		activeTag = '';
		goto('/wiki', { replaceState: true });
		loadPages();
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

		{#if allTags.length > 0}
			<div class="tag-chips">
				{#each allTags as tag}
					<button class="tag-chip" class:active={activeTag === tag} onclick={() => selectTag(tag)}>
						{tag}
					</button>
				{/each}
				{#if activeTag}
					<button class="tag-chip clear-chip" onclick={clearTag}>Clear filter</button>
				{/if}
			</div>
		{/if}

		{#if loading}
			<div class="loading-state">Loading wiki pages...</div>
		{:else if showFlat}
			{#if pages.length === 0}
				<div class="empty-state">
					{#if searchQuery}
						<p>No pages match your search.</p>
					{:else if activeTag}
						<p>No pages with tag "{activeTag}".</p>
					{/if}
				</div>
			{:else}
				<div class="page-list">
					{#each pages as p (p.id)}
						<a href="/wiki/{p.slug}" class="page-item">
							<div class="page-info">
								<div class="page-title">{p.title}</div>
								{#if p.tags && p.tags.length > 0}
									<div class="page-tags">
										{#each p.tags as tag}
											<span class="tag-pill">{tag}</span>
										{/each}
									</div>
								{/if}
							</div>
							<div class="page-meta">
								{#if p.updated_at}
									Updated {formatDate(p.updated_at)}
								{:else}
									Created {formatDate(p.created_at)}
								{/if}
							</div>
						</a>
					{/each}
				</div>
			{/if}
		{:else if treeNodes.length === 0 && pages.length === 0}
			<div class="empty-state">
				<p>No wiki pages yet.</p>
				<a href="/wiki/new" class="btn btn-secondary">Create your first page</a>
			</div>
		{:else}
			<WikiTreeView nodes={treeNodes} />
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

	.tag-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
		margin-bottom: 1.5rem;
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

	.tag-chip.clear-chip {
		border-style: dashed;
		color: var(--text-muted);
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

	.page-info {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-width: 0;
	}

	.page-title {
		font-size: 0.9375rem;
		font-weight: 500;
		color: var(--text-primary);
	}

	.page-tags {
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

	.page-meta {
		font-size: 0.75rem;
		color: var(--text-muted);
		white-space: nowrap;
		margin-left: 1rem;
	}
</style>
