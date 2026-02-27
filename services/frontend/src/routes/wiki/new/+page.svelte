<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { wiki } from '$lib/stores/wiki';
	import { toasts } from '$lib/stores/ui';
	import { renderMarkdown, extractWikiLinks } from '$lib/utils/markdown';
	import type { WikiTreeNode } from '$lib/types';

	let title = $state('');
	let content = $state('');
	let parentId: number | undefined = $state(undefined);
	let tagsInput = $state('');
	let saving = $state(false);
	let showPreview = $state(false);
	let renderedHtml = $state('');
	let resolvedSlugs: Record<string, string | null> = $state({});
	let eligibleParents: { id: number; title: string; depth: number }[] = $state([]);

	onMount(async () => {
		// Pre-fill title from query param (wiki-link create flow)
		const titleParam = $page.url.searchParams.get('title');
		if (titleParam) {
			title = titleParam;
		}

		// Pre-fill parent from query param
		const parentParam = $page.url.searchParams.get('parent');
		if (parentParam) {
			const parsed = parseInt(parentParam, 10);
			if (!isNaN(parsed)) {
				parentId = parsed;
			}
		}

		// Load tree for parent selector (only pages at depth <= 2 can be parents)
		try {
			const tree = await wiki.loadTree();
			const parents: { id: number; title: string; depth: number }[] = [];
			function collectParents(nodes: WikiTreeNode[], depth: number) {
				for (const node of nodes) {
					if (depth <= 2) {
						parents.push({ id: node.id, title: node.title, depth });
						collectParents(node.children, depth + 1);
					}
				}
			}
			collectParents(tree, 1);
			eligibleParents = parents;
		} catch {
			// Non-critical, parent selector just won't show options
		}
	});

	async function updatePreview() {
		if (!showPreview) return;
		const links = extractWikiLinks(content);
		if (links.length > 0) {
			resolvedSlugs = await wiki.resolveLinks(links);
		}
		renderedHtml = renderMarkdown(content, resolvedSlugs);
	}

	$effect(() => {
		if (showPreview) {
			updatePreview();
		}
	});

	async function handleSubmit() {
		if (!title.trim()) return;
		saving = true;
		try {
			const tags = tagsInput
				.split(',')
				.map((t) => t.trim())
				.filter(Boolean);
			const newPage = await wiki.add({
				title: title.trim(),
				content,
				parent_id: parentId,
				tags: tags.length > 0 ? tags : undefined
			});
			toasts.show('Page created', 'success');
			goto(`/wiki/${newPage.slug}`);
		} catch (error) {
			toasts.show('Failed to create page: ' + (error as Error).message, 'error');
		} finally {
			saving = false;
		}
	}

	function indentLabel(title: string, depth: number): string {
		return '\u00A0\u00A0'.repeat(depth - 1) + title;
	}
</script>

<svelte:head>
	<title>New Wiki Page - Task Manager</title>
</svelte:head>

<main class="container py-8">
	<div class="wiki-page">
		<a href="/wiki" class="back-link">&larr; Back to wiki</a>

		<h1>New Wiki Page</h1>

		<form
			onsubmit={(e) => {
				e.preventDefault();
				handleSubmit();
			}}
		>
			<div class="form-group">
				<label for="title" class="form-label">Title</label>
				<input
					id="title"
					type="text"
					bind:value={title}
					class="form-input"
					placeholder="Page title"
					required
					maxlength="500"
				/>
			</div>

			{#if eligibleParents.length > 0}
				<div class="form-group">
					<label for="parent" class="form-label">Parent Page</label>
					<select id="parent" bind:value={parentId} class="form-input">
						<option value={undefined}>None (root page)</option>
						{#each eligibleParents as p}
							<option value={p.id}>{indentLabel(p.title, p.depth)}</option>
						{/each}
					</select>
				</div>
			{/if}

			<div class="form-group">
				<label for="tags" class="form-label">Tags</label>
				<input
					id="tags"
					type="text"
					bind:value={tagsInput}
					class="form-input"
					placeholder="Comma-separated tags (e.g. design, frontend)"
				/>
			</div>

			<div class="form-group">
				<div class="editor-header">
					<label for="content" class="form-label">Content</label>
					<button
						type="button"
						class="preview-toggle"
						onclick={() => {
							showPreview = !showPreview;
						}}
					>
						{showPreview ? 'Edit' : 'Preview'}
					</button>
				</div>

				{#if showPreview}
					<div class="preview-pane wiki-content">
						{#if renderedHtml}
							{@html renderedHtml}
						{:else}
							<p class="text-muted">Nothing to preview</p>
						{/if}
					</div>
				{:else}
					<textarea
						id="content"
						bind:value={content}
						class="form-textarea"
						rows="16"
						placeholder="Write your content in Markdown. Use [[Page Title]] to link to other pages."
					></textarea>
				{/if}
			</div>

			<div class="form-actions">
				<a href="/wiki" class="btn btn-secondary">Cancel</a>
				<button type="submit" class="btn btn-primary" disabled={saving || !title.trim()}>
					{saving ? 'Creating...' : 'Create Page'}
				</button>
			</div>
		</form>
	</div>
</main>

<style>
	.wiki-page {
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

	h1 {
		font-size: 1.5rem;
		font-weight: 600;
		color: var(--text-primary);
		margin: 0 0 2rem 0;
	}

	.form-group {
		margin-bottom: 1.5rem;
	}

	.form-label {
		display: block;
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.05em;
		margin-bottom: 0.5rem;
	}

	.form-input,
	.form-textarea {
		width: 100%;
		padding: 0.625rem 0.875rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-input);
		color: var(--text-primary);
		font-size: 0.875rem;
		font-family: inherit;
	}

	.form-input:focus,
	.form-textarea:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 3px var(--primary-100);
	}

	select.form-input {
		cursor: pointer;
	}

	.form-textarea {
		resize: vertical;
		min-height: 200px;
		font-family: 'SF Mono', 'Fira Code', monospace;
		font-size: 0.8125rem;
		line-height: 1.6;
	}

	.editor-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.preview-toggle {
		background: none;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		padding: 0.25rem 0.75rem;
		font-size: 0.75rem;
		color: var(--text-secondary);
		cursor: pointer;
		transition: all var(--transition-fast);
	}

	.preview-toggle:hover {
		background: var(--bg-hover);
		color: var(--text-primary);
	}

	.preview-pane {
		min-height: 200px;
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-card);
	}

	.form-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
	}
</style>
