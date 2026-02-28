<script lang="ts">
	import { onMount } from 'svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { snippets } from '$lib/stores/snippets';
	import { toasts } from '$lib/stores/ui';
	import type { Snippet } from '$lib/types';

	let snippet: Snippet | null = $state(null);
	let loading = $state(true);
	let error = $state('');
	let confirmDelete = $state(false);

	let snippetId = $derived(parseInt($page.params.id ?? '0', 10));

	onMount(async () => {
		await loadSnippet();
	});

	async function loadSnippet() {
		loading = true;
		error = '';
		try {
			snippet = await snippets.getById(snippetId);
		} catch (e) {
			error = (e as Error).message || 'Snippet not found';
		} finally {
			loading = false;
		}
	}

	async function handleDelete() {
		if (!confirmDelete) {
			confirmDelete = true;
			return;
		}
		try {
			await snippets.remove(snippetId);
			toasts.show('Snippet deleted', 'success');
			goto('/snippets');
		} catch (e) {
			toasts.show('Failed to delete: ' + (e as Error).message, 'error');
		}
	}

	function cancelDelete() {
		confirmDelete = false;
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return '';
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

	function formatTimestamp(dateStr: string | null): string {
		if (!dateStr) return '';
		return new Date(dateStr).toLocaleString();
	}
</script>

<svelte:head>
	<title>{snippet ? snippet.title : 'Snippet'} - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="snippet-view-page">
		{#if loading}
			<div class="loading-state">Loading snippet...</div>
		{:else if error}
			<div class="error-state">
				<p>{error}</p>
				<a href="/snippets" class="btn btn-secondary">Back to Snippets</a>
			</div>
		{:else if snippet}
			<div class="view-header">
				<a href="/snippets" class="back-link">&larr; Back to Snippets</a>
			</div>

			<div class="snippet-detail">
				<div class="detail-header">
					<div>
						<span class="snippet-category">{snippet.category}</span>
						<h1>{snippet.title}</h1>
					</div>
					<div class="detail-actions">
						<a href="/snippets/{snippet.id}/edit" class="btn btn-secondary btn-sm">Edit</a>
						{#if confirmDelete}
							<button class="btn btn-danger btn-sm" onclick={handleDelete}> Confirm Delete </button>
							<button class="btn btn-secondary btn-sm" onclick={cancelDelete}>Cancel</button>
						{:else}
							<button class="btn btn-danger btn-sm" onclick={handleDelete}>Delete</button>
						{/if}
					</div>
				</div>

				<div class="detail-meta">
					<div class="meta-item">
						<span class="meta-label">Date:</span>
						<span class="meta-value">{formatDate(snippet.snippet_date)}</span>
					</div>
					{#if snippet.updated_at}
						<div class="meta-item">
							<span class="meta-label">Updated:</span>
							<span class="meta-value">{formatTimestamp(snippet.updated_at)}</span>
						</div>
					{:else}
						<div class="meta-item">
							<span class="meta-label">Created:</span>
							<span class="meta-value">{formatTimestamp(snippet.created_at)}</span>
						</div>
					{/if}
				</div>

				{#if snippet.tags && snippet.tags.length > 0}
					<div class="detail-tags">
						{#each snippet.tags as tag}
							<a href="/snippets?tag={encodeURIComponent(tag)}" class="tag-chip">{tag}</a>
						{/each}
					</div>
				{/if}

				{#if snippet.content}
					<div class="detail-content">
						<p>{snippet.content}</p>
					</div>
				{/if}
			</div>
		{/if}
	</div>
</main>

<style>
	.snippet-view-page {
		max-width: 700px;
		margin: 0 auto;
	}

	.loading-state,
	.error-state {
		text-align: center;
		padding: 4rem 2rem;
		color: var(--text-secondary);
	}

	.error-state p {
		margin-bottom: 1rem;
	}

	.view-header {
		margin-bottom: 1rem;
	}

	.back-link {
		font-size: 0.8125rem;
		color: var(--text-muted);
		text-decoration: none;
	}

	.back-link:hover {
		color: var(--primary-600);
	}

	.snippet-detail {
		background: var(--bg-card);
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		padding: 1.5rem;
	}

	.detail-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 1rem;
	}

	.detail-header h1 {
		font-size: 1.375rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0.375rem 0 0 0;
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
	}

	.detail-actions {
		display: flex;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.btn-sm {
		font-size: 0.8125rem;
		padding: 0.375rem 0.75rem;
	}

	.btn-danger {
		background: var(--red-500, #ef4444);
		color: white;
		border: none;
		border-radius: var(--radius);
		cursor: pointer;
	}

	.btn-danger:hover {
		background: var(--red-600, #dc2626);
	}

	.detail-meta {
		display: flex;
		gap: 1.5rem;
		margin-bottom: 1rem;
		font-size: 0.8125rem;
	}

	.meta-label {
		color: var(--text-muted);
		margin-right: 0.25rem;
	}

	.meta-value {
		color: var(--text-secondary);
	}

	.detail-tags {
		display: flex;
		flex-wrap: wrap;
		gap: 0.375rem;
		margin-bottom: 1rem;
	}

	.tag-chip {
		font-size: 0.75rem;
		padding: 0.25rem 0.625rem;
		border-radius: 9999px;
		background: var(--primary-100);
		color: var(--primary-700);
		text-decoration: none;
		transition: all var(--transition-fast);
	}

	.tag-chip:hover {
		background: var(--primary-200);
	}

	.detail-content {
		padding-top: 1rem;
		border-top: 1px solid var(--border-color);
		color: var(--text-primary);
		font-size: 0.9375rem;
		line-height: 1.6;
		white-space: pre-wrap;
	}

	.detail-content p {
		margin: 0;
	}
</style>
