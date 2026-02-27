<script lang="ts">
	import type { WikiTreeNode } from '$lib/types';

	interface Props {
		nodes: WikiTreeNode[];
		depth?: number;
	}

	let { nodes, depth = 0 }: Props = $props();

	let expanded = $state(new Set<number>());

	// Auto-expand root nodes on first render
	$effect(() => {
		if (depth === 0) {
			const rootIds = new Set(nodes.map((n) => n.id));
			expanded = rootIds;
		}
	});

	function toggle(id: number) {
		const next = new Set(expanded);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		expanded = next;
	}
</script>

<ul class="tree-list" class:root={depth === 0}>
	{#each nodes as node (node.id)}
		<li class="tree-node">
			<div class="node-row">
				{#if node.children.length > 0}
					<button
						class="toggle-btn"
						onclick={() => toggle(node.id)}
						aria-label={expanded.has(node.id) ? 'Collapse' : 'Expand'}
					>
						<span class="chevron" class:open={expanded.has(node.id)}>&#9656;</span>
					</button>
				{:else}
					<span class="toggle-spacer"></span>
				{/if}
				<a href="/wiki/{node.slug}" class="node-link">
					<span class="node-title">{node.title}</span>
				</a>
				{#if node.tags.length > 0}
					<span class="node-tags">
						{#each node.tags as tag}
							<span class="tag-pill">{tag}</span>
						{/each}
					</span>
				{/if}
			</div>
			{#if node.children.length > 0 && expanded.has(node.id)}
				<svelte:self nodes={node.children} depth={depth + 1} />
			{/if}
		</li>
	{/each}
</ul>

<style>
	.tree-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.tree-list:not(.root) {
		padding-left: 1.25rem;
		border-left: 1px solid var(--border-color);
		margin-left: 0.5rem;
	}

	.tree-node {
		margin: 0;
	}

	.node-row {
		display: flex;
		align-items: center;
		gap: 0.25rem;
		padding: 0.375rem 0.5rem;
		border-radius: var(--radius);
		transition: background var(--transition-fast);
	}

	.node-row:hover {
		background: var(--bg-hover);
	}

	.toggle-btn {
		background: none;
		border: none;
		padding: 0;
		width: 1.25rem;
		height: 1.25rem;
		display: flex;
		align-items: center;
		justify-content: center;
		cursor: pointer;
		color: var(--text-muted);
		flex-shrink: 0;
	}

	.toggle-btn:hover {
		color: var(--text-primary);
	}

	.chevron {
		display: inline-block;
		transition: transform 0.15s ease;
		font-size: 0.75rem;
	}

	.chevron.open {
		transform: rotate(90deg);
	}

	.toggle-spacer {
		width: 1.25rem;
		flex-shrink: 0;
	}

	.node-link {
		text-decoration: none;
		flex: 1;
		min-width: 0;
	}

	.node-title {
		font-size: 0.9375rem;
		font-weight: 500;
		color: var(--text-primary);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.node-link:hover .node-title {
		color: var(--primary-600);
	}

	.node-tags {
		display: flex;
		gap: 0.25rem;
		flex-shrink: 0;
		margin-left: 0.5rem;
	}

	.tag-pill {
		font-size: 0.625rem;
		padding: 0.0625rem 0.375rem;
		border-radius: 9999px;
		background: var(--primary-100);
		color: var(--primary-700);
		white-space: nowrap;
	}
</style>
