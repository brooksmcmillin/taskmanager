<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { snippets } from '$lib/stores/snippets';
	import { toasts } from '$lib/stores/ui';
	import type { CategoryCount } from '$lib/types';

	let category = $state('');
	let title = $state('');
	let content = $state('');
	let snippetDate = $state('');
	let tagsInput = $state('');
	let saving = $state(false);
	let existingCategories: CategoryCount[] = $state([]);

	onMount(async () => {
		// Pre-fill from query params
		const catParam = $page.url.searchParams.get('category');
		if (catParam) category = catParam;

		// Set default date to today
		const now = new Date();
		const y = now.getFullYear();
		const m = String(now.getMonth() + 1).padStart(2, '0');
		const d = String(now.getDate()).padStart(2, '0');
		snippetDate = `${y}-${m}-${d}`;

		// Load existing categories for suggestions
		try {
			existingCategories = await snippets.getCategories();
		} catch {
			// Non-critical
		}
	});

	async function handleSubmit() {
		if (!category.trim() || !title.trim()) return;
		saving = true;
		try {
			const tags = tagsInput
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean);

			const newSnippet = await snippets.add({
				category: category.trim(),
				title: title.trim(),
				content: content || undefined,
				snippet_date: snippetDate || undefined,
				tags: tags.length > 0 ? tags : undefined
			});

			toasts.show('Snippet created!', 'success');
			goto(`/snippets/${newSnippet.id}`);
		} catch (error) {
			toasts.show('Failed to create snippet: ' + (error as Error).message, 'error');
		} finally {
			saving = false;
		}
	}
</script>

<svelte:head>
	<title>New Snippet - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="snippet-form-page">
		<div class="form-header">
			<a href="/snippets" class="back-link">&larr; Back to Snippets</a>
			<h1>New Snippet</h1>
		</div>

		<form onsubmit={handleSubmit}>
			<div class="form-group">
				<label for="category">Category</label>
				<input
					id="category"
					type="text"
					bind:value={category}
					placeholder="e.g., Car Maintenance, House, Health"
					maxlength="255"
					required
					list="category-suggestions"
				/>
				{#if existingCategories.length > 0}
					<datalist id="category-suggestions">
						{#each existingCategories as cat}
							<option value={cat.category}></option>
						{/each}
					</datalist>
				{/if}
			</div>

			<div class="form-group">
				<label for="title">Title</label>
				<input
					id="title"
					type="text"
					bind:value={title}
					placeholder="e.g., Changed air filter"
					maxlength="500"
					required
				/>
			</div>

			<div class="form-group">
				<label for="snippet-date">Date</label>
				<input id="snippet-date" type="date" bind:value={snippetDate} />
			</div>

			<div class="form-group">
				<label for="content">Notes <span class="optional">(optional)</span></label>
				<textarea id="content" bind:value={content} placeholder="Any additional details..." rows="4"
				></textarea>
			</div>

			<div class="form-group">
				<label for="tags">Tags <span class="optional">(optional, comma-separated)</span></label>
				<input
					id="tags"
					type="text"
					bind:value={tagsInput}
					placeholder="e.g., filter, maintenance"
				/>
			</div>

			<div class="form-actions">
				<a href="/snippets" class="btn btn-secondary">Cancel</a>
				<button
					type="submit"
					class="btn btn-primary"
					disabled={saving || !category.trim() || !title.trim()}
				>
					{saving ? 'Saving...' : 'Create Snippet'}
				</button>
			</div>
		</form>
	</div>
</main>

<style>
	.snippet-form-page {
		max-width: 600px;
		margin: 0 auto;
	}

	.form-header {
		margin-bottom: 1.5rem;
	}

	.back-link {
		font-size: 0.8125rem;
		color: var(--text-muted);
		text-decoration: none;
		display: inline-block;
		margin-bottom: 0.5rem;
	}

	.back-link:hover {
		color: var(--primary-600);
	}

	.form-header h1 {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0;
	}

	.form-group {
		margin-bottom: 1.25rem;
	}

	.form-group label {
		display: block;
		font-size: 0.8125rem;
		font-weight: 500;
		color: var(--text-secondary);
		margin-bottom: 0.375rem;
	}

	.optional {
		font-weight: 400;
		color: var(--text-muted);
	}

	.form-group input,
	.form-group textarea {
		width: 100%;
		padding: 0.625rem 0.875rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-input);
		color: var(--text-primary);
		font-size: 0.875rem;
	}

	.form-group textarea {
		resize: vertical;
		font-family: inherit;
	}

	.form-group input:focus,
	.form-group textarea:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 3px var(--primary-100);
	}

	.form-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 1.5rem;
	}
</style>
