<script lang="ts">
	import Modal from './Modal.svelte';
	import { wiki } from '$lib/stores/wiki';
	import { toasts } from '$lib/stores/ui';
	import type { WikiPage, WikiTreeNode } from '$lib/types';

	let { onMoved }: { onMoved?: () => void } = $props();

	let modal: Modal;
	let page: WikiPage | null = null;
	let selectedParentId: number | null = null;
	let eligibleParents: { id: number; title: string; depth: number }[] = [];
	let loading = false;
	let saving = false;

	const MAX_WIKI_DEPTH = 3;

	function collectDescendantIds(nodes: WikiTreeNode[], targetId: number): Set<number> {
		const ids = new Set<number>();
		function walk(nodeList: WikiTreeNode[], collecting: boolean) {
			for (const node of nodeList) {
				if (node.id === targetId || collecting) {
					ids.add(node.id);
					walk(node.children, true);
				} else {
					walk(node.children, false);
				}
			}
		}
		walk(nodes, false);
		return ids;
	}

	function getSubtreeDepth(nodes: WikiTreeNode[], targetId: number): number {
		function findNode(nodeList: WikiTreeNode[]): WikiTreeNode | null {
			for (const node of nodeList) {
				if (node.id === targetId) return node;
				const found = findNode(node.children);
				if (found) return found;
			}
			return null;
		}
		function maxDepth(node: WikiTreeNode): number {
			if (node.children.length === 0) return 0;
			return 1 + Math.max(...node.children.map(maxDepth));
		}
		const node = findNode(nodes);
		return node ? maxDepth(node) : 0;
	}

	export async function open(wikiPage: WikiPage) {
		page = wikiPage;
		selectedParentId = wikiPage.parent_id;
		loading = true;
		saving = false;
		modal.openModal();

		try {
			const tree = await wiki.loadTree();
			const selfAndDescendants = collectDescendantIds(tree, wikiPage.id);
			const subtreeDepth = getSubtreeDepth(tree, wikiPage.id);
			const maxParentDepth = MAX_WIKI_DEPTH - subtreeDepth - 1;
			const parents: { id: number; title: string; depth: number }[] = [];
			function collectParents(nodes: WikiTreeNode[], depth: number) {
				for (const node of nodes) {
					if (!selfAndDescendants.has(node.id) && depth <= maxParentDepth) {
						parents.push({ id: node.id, title: node.title, depth });
						collectParents(node.children, depth + 1);
					}
				}
			}
			collectParents(tree, 1);
			eligibleParents = parents;
		} catch {
			toasts.show('Failed to load pages', 'error');
		} finally {
			loading = false;
		}
	}

	function indentLabel(title: string, depth: number): string {
		return '\u00A0\u00A0'.repeat(depth - 1) + title;
	}

	async function handleMove() {
		if (!page) return;
		if (selectedParentId === page.parent_id) {
			modal.closeModal();
			return;
		}
		saving = true;
		try {
			await wiki.movePage(page.id, selectedParentId);
			toasts.show('Page moved', 'success');
			modal.closeModal();
			onMoved?.();
		} catch (e) {
			toasts.show('Failed to move page: ' + (e as Error).message, 'error');
		} finally {
			saving = false;
		}
	}

	function handleClose() {
		page = null;
		eligibleParents = [];
	}
</script>

<Modal bind:this={modal} title="Move Page" on:close={handleClose}>
	{#if loading}
		<p class="loading-text">Loading pages...</p>
	{:else}
		<div class="move-form">
			<label for="move-parent" class="form-label">New Parent</label>
			<select id="move-parent" class="form-input" bind:value={selectedParentId}>
				<option value={null}>None (root page)</option>
				{#each eligibleParents as p}
					<option value={p.id}>{indentLabel(p.title, p.depth)}</option>
				{/each}
			</select>
			<div class="move-actions">
				<button class="btn btn-secondary btn-med" on:click={() => modal.closeModal()}>Cancel</button
				>
				<button class="btn btn-primary btn-med" on:click={handleMove} disabled={saving}>
					{saving ? 'Moving...' : 'Move'}
				</button>
			</div>
		</div>
	{/if}
</Modal>

<style>
	.loading-text {
		color: var(--text-secondary);
		text-align: center;
		padding: 1rem 0;
	}

	.move-form {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.form-label {
		font-size: 0.75rem;
		font-weight: 600;
		color: var(--text-secondary);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.form-input {
		width: 100%;
		padding: 0.625rem 0.875rem;
		border: 1px solid var(--border-color);
		border-radius: var(--radius);
		background: var(--bg-input);
		color: var(--text-primary);
		font-size: 0.875rem;
		font-family: inherit;
		cursor: pointer;
	}

	.form-input:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 3px var(--primary-100);
	}

	.move-actions {
		display: flex;
		justify-content: flex-end;
		gap: 0.75rem;
		margin-top: 0.5rem;
	}
</style>
