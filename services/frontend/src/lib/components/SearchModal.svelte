<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api/client';
	import { getPriorityColor } from '$lib/utils/priority';
	import { logger } from '$lib/utils/logger';

	interface UnifiedSearchItem {
		type: string;
		id: number;
		title: string;
		subtitle: string | null;
		url: string;
		metadata: Record<string, unknown>;
	}

	const TYPE_LABELS: Record<string, string> = {
		task: 'Tasks',
		wiki: 'Wiki Pages',
		snippet: 'Snippets',
		article: 'Articles'
	};

	const TYPE_ORDER = ['task', 'wiki', 'snippet', 'article'];

	export let open = false;

	const dispatch = createEventDispatcher<{ close: void }>();

	let query = '';
	let groupedResults: Record<string, UnifiedSearchItem[]> = {};
	let loading = false;
	let searched = false;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let inputEl: HTMLInputElement;

	$: totalResults = Object.values(groupedResults).reduce((sum, items) => sum + items.length, 0);

	function close() {
		open = false;
		query = '';
		groupedResults = {};
		searched = false;
		loading = false;
		dispatch('close');
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			close();
		}
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			close();
		}
	}

	async function search(q: string) {
		if (!q.trim()) {
			groupedResults = {};
			searched = false;
			loading = false;
			return;
		}

		loading = true;
		try {
			const response = await api.get<{
				data: { results: Record<string, UnifiedSearchItem[]>; meta: { total: number } };
			}>('/api/search', {
				params: { q: q.trim() }
			});
			groupedResults = response.data?.results || {};
			searched = true;
		} catch (error) {
			logger.error('Search failed:', error);
			groupedResults = {};
			searched = true;
		} finally {
			loading = false;
		}
	}

	function handleInput() {
		clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			search(query);
		}, 300);
	}

	function selectResult(item: UnifiedSearchItem) {
		close();
		if (item.metadata?.external) {
			window.open(item.url, '_blank', 'noopener');
		} else {
			goto(item.url);
		}
	}

	onDestroy(() => clearTimeout(debounceTimer));

	$: if (open) {
		// Focus input when modal opens
		setTimeout(() => inputEl?.focus(), 50);
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if open}
	<div
		class="search-backdrop"
		on:click={handleBackdropClick}
		role="presentation"
		aria-hidden="true"
	>
		<div
			class="search-modal"
			role="dialog"
			aria-modal="true"
			aria-label="Search tasks, wiki, snippets, and articles"
		>
			<div class="search-input-wrapper">
				<svg
					class="search-icon"
					xmlns="http://www.w3.org/2000/svg"
					viewBox="0 0 20 20"
					fill="currentColor"
				>
					<path
						fill-rule="evenodd"
						d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
						clip-rule="evenodd"
					/>
				</svg>
				<input
					bind:this={inputEl}
					bind:value={query}
					on:input={handleInput}
					type="text"
					class="search-input"
					placeholder="Search tasks, wiki, snippets, and articles..."
					autocomplete="off"
					spellcheck="false"
				/>
				<kbd class="search-kbd">Esc</kbd>
			</div>

			<div class="search-results">
				{#if loading}
					<div class="search-state">
						<div class="search-spinner"></div>
						Searching...
					</div>
				{:else if searched && totalResults === 0}
					<div class="search-state">No results found</div>
				{:else if totalResults > 0}
					{#each TYPE_ORDER as type}
						{#if groupedResults[type]?.length}
							<div class="result-group">
								<div class="result-group-header">
									<span class="result-group-label">{TYPE_LABELS[type]}</span>
									<span class="result-group-count">{groupedResults[type].length}</span>
								</div>
								{#each groupedResults[type] as item}
									<button class="search-result" on:click={() => selectResult(item)}>
										<div class="result-left">
											{#if item.type === 'task' && item.metadata?.priority}
												<span
													class="result-priority"
													style="background-color: {getPriorityColor(
														String(item.metadata.priority)
													)}"
												></span>
											{/if}
											<div class="result-content">
												<div class="result-title">{item.title}</div>
												{#if item.subtitle}
													<div class="result-subtitle">{item.subtitle}</div>
												{/if}
											</div>
										</div>
										{#if item.metadata?.external}
											<svg
												class="external-icon"
												xmlns="http://www.w3.org/2000/svg"
												viewBox="0 0 20 20"
												fill="currentColor"
											>
												<path
													fill-rule="evenodd"
													d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5zm7.25-.75a.75.75 0 01.75-.75h3.5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0V6.31l-5.47 5.47a.75.75 0 01-1.06-1.06l5.47-5.47H12.25a.75.75 0 01-.75-.75z"
													clip-rule="evenodd"
												/>
											</svg>
										{/if}
									</button>
								{/each}
							</div>
						{/if}
					{/each}
				{:else}
					<div class="search-state search-hint">
						Type to search tasks, wiki, snippets, and articles
					</div>
				{/if}
			</div>
		</div>
	</div>
{/if}

<style>
	.search-backdrop {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.4);
		z-index: 1000;
		display: flex;
		align-items: flex-start;
		justify-content: center;
		padding-top: 15vh;
	}

	.search-modal {
		background: var(--bg-card, #fff);
		border: 1px solid var(--border-color, #e5e7eb);
		border-radius: var(--radius-lg, 0.75rem);
		box-shadow: 0 16px 48px rgba(0, 0, 0, 0.15);
		width: 100%;
		max-width: 36rem;
		max-height: 60vh;
		display: flex;
		flex-direction: column;
		overflow: hidden;
		animation: searchIn 0.15s ease-out;
	}

	@keyframes searchIn {
		from {
			opacity: 0;
			transform: scale(0.97) translateY(-8px);
		}
		to {
			opacity: 1;
			transform: scale(1) translateY(0);
		}
	}

	.search-input-wrapper {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		padding: 0.875rem 1rem;
		border-bottom: 1px solid var(--border-color, #e5e7eb);
	}

	.search-icon {
		width: 1.25rem;
		height: 1.25rem;
		color: var(--text-muted, #9ca3af);
		flex-shrink: 0;
	}

	.search-input {
		flex: 1;
		border: none;
		outline: none;
		font-size: 1rem;
		background: transparent;
		color: var(--text-primary, #1f2937);
	}

	.search-input::placeholder {
		color: var(--text-muted, #9ca3af);
	}

	.search-kbd {
		font-size: 0.6875rem;
		font-weight: 500;
		padding: 0.125rem 0.375rem;
		border: 1px solid var(--border-color, #e5e7eb);
		border-radius: var(--radius, 0.25rem);
		color: var(--text-muted, #9ca3af);
		background: var(--bg-page, #f9fafb);
	}

	.search-results {
		overflow-y: auto;
		max-height: calc(60vh - 4rem);
	}

	.search-state {
		padding: 2rem 1rem;
		text-align: center;
		color: var(--text-muted, #9ca3af);
		font-size: 0.875rem;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
	}

	.search-hint {
		padding: 1.5rem 1rem;
	}

	.search-spinner {
		width: 1rem;
		height: 1rem;
		border: 2px solid var(--border-color, #e5e7eb);
		border-top-color: var(--primary-500, #3b82f6);
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	/* Result groups */
	.result-group {
		border-bottom: 1px solid var(--border-color, #e5e7eb);
	}

	.result-group:last-child {
		border-bottom: none;
	}

	.result-group-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 1rem;
		background: var(--bg-page, #f9fafb);
	}

	.result-group-label {
		font-size: 0.6875rem;
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		color: var(--text-muted, #9ca3af);
	}

	.result-group-count {
		font-size: 0.625rem;
		font-weight: 600;
		padding: 0.0625rem 0.375rem;
		border-radius: 9999px;
		background: var(--border-color, #e5e7eb);
		color: var(--text-muted, #6b7280);
	}

	.search-result {
		display: flex;
		align-items: center;
		justify-content: space-between;
		width: 100%;
		padding: 0.625rem 1rem;
		border: none;
		background: none;
		cursor: pointer;
		text-align: left;
		transition: background 0.1s ease;
		font-family: inherit;
		color: inherit;
	}

	.search-result:hover {
		background: var(--bg-hover, #f3f4f6);
	}

	.result-left {
		display: flex;
		align-items: flex-start;
		gap: 0.625rem;
		min-width: 0;
		flex: 1;
	}

	.result-priority {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		flex-shrink: 0;
		margin-top: 0.375rem;
	}

	.result-content {
		min-width: 0;
		flex: 1;
	}

	.result-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--text-primary, #1f2937);
		line-height: 1.4;
	}

	.result-subtitle {
		font-size: 0.75rem;
		color: var(--text-muted, #9ca3af);
		margin-top: 0.125rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.external-icon {
		width: 0.875rem;
		height: 0.875rem;
		color: var(--text-muted, #9ca3af);
		flex-shrink: 0;
		margin-left: 0.5rem;
	}

	@media (max-width: 768px) {
		.search-backdrop {
			padding-top: 5vh;
			padding-left: 1rem;
			padding-right: 1rem;
		}
	}
</style>
