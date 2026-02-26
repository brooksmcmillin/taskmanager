<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { wiki } from '$lib/stores/wiki';
	import { toasts } from '$lib/stores/ui';
	import { renderMarkdown, extractWikiLinks } from '$lib/utils/markdown';
	import type { WikiPage, WikiLinkedTodo } from '$lib/types';

	let wikiPage: WikiPage | null = $state(null);
	let linkedTasks: WikiLinkedTodo[] = $state([]);
	let loading = $state(true);
	let error = $state('');
	let renderedHtml = $state('');
	let confirmDelete = $state(false);

	let slug = $derived($page.params.slug ?? '');

	$effect(() => {
		if (slug) {
			loadPage();
		}
	});

	async function loadPage() {
		loading = true;
		error = '';
		try {
			wikiPage = await wiki.getBySlug(slug);
			await renderContent();
			linkedTasks = await wiki.getLinkedTasks(wikiPage.id);
		} catch {
			error = 'Page not found';
		} finally {
			loading = false;
		}
	}

	async function renderContent() {
		if (!wikiPage) return;
		const links = extractWikiLinks(wikiPage.content);
		let resolved: Record<string, string | null> = {};
		if (links.length > 0) {
			resolved = await wiki.resolveLinks(links);
		}
		renderedHtml = renderMarkdown(wikiPage.content, resolved);
	}

	async function handleDelete() {
		if (!wikiPage) return;
		try {
			await wiki.remove(wikiPage.id);
			toasts.show('Page deleted', 'success');
			goto('/wiki');
		} catch (e) {
			toasts.show('Failed to delete page: ' + (e as Error).message, 'error');
		}
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
		return new Date(dateStr).toLocaleString();
	}
</script>

<svelte:head>
	<title>{wikiPage ? wikiPage.title : 'Wiki'} - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="wiki-view">
		<a href="/wiki" class="back-link">&larr; Back to wiki</a>

		{#if loading}
			<div class="loading-state">Loading page...</div>
		{:else if error}
			<div class="error-state">
				<p>{error}</p>
				<a href="/wiki" class="btn btn-secondary">Back to wiki</a>
			</div>
		{:else if wikiPage}
			<div class="page-header">
				<h1>{wikiPage.title}</h1>
				<div class="page-actions">
					<a href="/wiki/{wikiPage.slug}/edit" class="btn btn-secondary btn-med">Edit</a>
					{#if confirmDelete}
						<button class="btn btn-danger btn-med" onclick={handleDelete}>Confirm Delete</button>
						<button class="btn btn-secondary btn-med" onclick={() => (confirmDelete = false)}
							>Cancel</button
						>
					{:else}
						<button class="btn btn-danger-outline btn-med" onclick={() => (confirmDelete = true)}
							>Delete</button
						>
					{/if}
				</div>
			</div>

			<div class="page-meta-bar">
				{#if wikiPage.updated_at}
					<span>Updated {formatDate(wikiPage.updated_at)}</span>
				{:else}
					<span>Created {formatDate(wikiPage.created_at)}</span>
				{/if}
			</div>

			<div class="page-content wiki-content">
				{#if renderedHtml}
					{@html renderedHtml}
				{:else}
					<p class="text-muted">This page has no content yet.</p>
				{/if}
			</div>

			<!-- Linked Tasks -->
			{#if linkedTasks.length > 0}
				<div class="linked-section">
					<h2>Linked Tasks</h2>
					<div class="linked-list">
						{#each linkedTasks as task (task.id)}
							<a href="/task/{task.id}" class="linked-item">
								<span class="linked-title">{task.title}</span>
								<span class="linked-status capitalize">{task.status.replace('_', ' ')}</span>
							</a>
						{/each}
					</div>
				</div>
			{/if}
		{/if}
	</div>
</main>

<style>
	.wiki-view {
		max-width: 800px;
		margin: 0 auto;
	}

	.back-link {
		display: inline-block;
		color: var(--text-secondary);
		text-decoration: none;
		font-size: 0.875rem;
		margin-bottom: 1.5rem;
		transition: color var(--transition-fast);
	}

	.back-link:hover {
		color: var(--primary-600);
	}

	.loading-state,
	.error-state {
		text-align: center;
		padding: 4rem 2rem;
		color: var(--text-secondary);
	}

	.error-state p {
		margin-bottom: 1.5rem;
		font-size: 1.125rem;
	}

	.page-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: 1rem;
		margin-bottom: 0.5rem;
	}

	.page-header h1 {
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--text-primary);
		margin: 0;
		line-height: 1.3;
	}

	.page-actions {
		display: flex;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.page-meta-bar {
		font-size: 0.75rem;
		color: var(--text-muted);
		margin-bottom: 2rem;
	}

	.page-content {
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius-lg);
		padding: 2rem;
		line-height: 1.7;
	}

	/* Wiki content typography */
	.wiki-content :global(h1) {
		font-size: 1.5rem;
		font-weight: 700;
		margin: 1.5rem 0 0.75rem;
		color: var(--text-primary);
	}

	.wiki-content :global(h2) {
		font-size: 1.25rem;
		font-weight: 600;
		margin: 1.25rem 0 0.625rem;
		color: var(--text-primary);
	}

	.wiki-content :global(h3) {
		font-size: 1.0625rem;
		font-weight: 600;
		margin: 1rem 0 0.5rem;
		color: var(--text-primary);
	}

	.wiki-content :global(p) {
		margin: 0.75rem 0;
		color: var(--text-primary);
	}

	.wiki-content :global(ul),
	.wiki-content :global(ol) {
		margin: 0.75rem 0;
		padding-left: 1.5rem;
	}

	.wiki-content :global(li) {
		margin: 0.25rem 0;
	}

	.wiki-content :global(code) {
		background: var(--bg-hover);
		padding: 0.125rem 0.375rem;
		border-radius: var(--radius-sm, 3px);
		font-size: 0.8125rem;
	}

	.wiki-content :global(pre) {
		background: var(--bg-hover);
		padding: 1rem;
		border-radius: var(--radius);
		overflow-x: auto;
		margin: 1rem 0;
	}

	.wiki-content :global(pre code) {
		background: none;
		padding: 0;
	}

	.wiki-content :global(blockquote) {
		border-left: 3px solid var(--primary-400);
		margin: 1rem 0;
		padding: 0.5rem 1rem;
		color: var(--text-secondary);
	}

	.wiki-content :global(a) {
		color: var(--primary-600);
		text-decoration: underline;
	}

	.wiki-content :global(a:hover) {
		color: var(--primary-700);
	}

	/* Wiki links */
	.wiki-content :global(.wiki-link) {
		color: var(--primary-600);
		text-decoration: underline;
	}

	.wiki-content :global(.wiki-link-missing) {
		color: var(--error-600, #dc2626);
		text-decoration: underline;
		text-decoration-style: dashed;
	}

	/* Linked tasks section */
	.linked-section {
		margin-top: 2rem;
	}

	.linked-section h2 {
		font-size: 1rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0 0 0.75rem 0;
	}

	.linked-list {
		display: flex;
		flex-direction: column;
		gap: 0.375rem;
	}

	.linked-item {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.625rem 0.875rem;
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		text-decoration: none;
		transition: all var(--transition-fast);
	}

	.linked-item:hover {
		border-color: var(--primary-300);
		background: var(--bg-hover);
	}

	.linked-title {
		font-size: 0.875rem;
		color: var(--text-primary);
	}

	.linked-status {
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.btn-danger-outline {
		background: transparent;
		color: var(--error-600, #dc2626);
		border: 1px solid var(--error-600, #dc2626);
	}

	.btn-danger-outline:hover {
		background: var(--error-600, #dc2626);
		color: white;
	}

	@media (max-width: 640px) {
		.page-header {
			flex-direction: column;
		}

		.page-content {
			padding: 1.5rem;
		}
	}
</style>
