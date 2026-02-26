<script lang="ts">
	import { createEventDispatcher, onDestroy } from 'svelte';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api/client';
	import { getPriorityColor } from '$lib/utils/priority';
	import { formatDateDisplay } from '$lib/utils/dates';
	import { logger } from '$lib/utils/logger';

	interface SearchResult {
		id: number;
		title: string;
		description: string | null;
		status: string;
		priority: string;
		due_date: string | null;
		project_name: string | null;
		project_color: string | null;
		tags: string[];
	}

	export let open = false;

	const dispatch = createEventDispatcher<{ close: void }>();

	let query = '';
	let results: SearchResult[] = [];
	let loading = false;
	let searched = false;
	let debounceTimer: ReturnType<typeof setTimeout>;
	let inputEl: HTMLInputElement;

	function close() {
		open = false;
		query = '';
		results = [];
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
			results = [];
			searched = false;
			loading = false;
			return;
		}

		loading = true;
		try {
			const response = await api.get<{ data: SearchResult[] }>('/api/tasks/search', {
				params: { q: q.trim() }
			});
			results = response.data || [];
			searched = true;
		} catch (error) {
			logger.error('Search failed:', error);
			results = [];
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

	function selectResult(id: number) {
		close();
		goto(`/task/${id}`);
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
		<div class="search-modal" role="dialog" aria-modal="true" aria-label="Search tasks">
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
					placeholder="Search tasks..."
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
				{:else if searched && results.length === 0}
					<div class="search-state">No results found</div>
				{:else if results.length > 0}
					{#each results as result}
						<button class="search-result" on:click={() => selectResult(result.id)}>
							<div class="result-left">
								<span
									class="result-priority"
									style="background-color: {getPriorityColor(result.priority)}"
								></span>
								<div class="result-content">
									<div class="result-title">{result.title}</div>
									<div class="result-meta">
										<span class="result-status {result.status}"
											>{result.status.replaceAll('_', ' ')}</span
										>
										{#if result.project_name}
											<span class="result-project">{result.project_name}</span>
										{/if}
										{#if result.due_date}
											<span class="result-due">Due: {formatDateDisplay(result.due_date)}</span>
										{/if}
									</div>
								</div>
							</div>
						</button>
					{/each}
				{:else}
					<div class="search-state search-hint">Type to search tasks by title or description</div>
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
	}

	.result-title {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--text-primary, #1f2937);
		line-height: 1.4;
	}

	.result-meta {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-top: 0.125rem;
		font-size: 0.75rem;
		color: var(--text-muted, #9ca3af);
	}

	.result-status {
		font-size: 0.6875rem;
		font-weight: 500;
		padding: 0.0625rem 0.375rem;
		border-radius: var(--radius, 0.25rem);
		text-transform: capitalize;
	}

	.result-status.pending {
		background: var(--gray-100, #f3f4f6);
		color: var(--text-muted, #6b7280);
	}

	.result-status.in_progress {
		background: var(--primary-50, #eff6ff);
		color: var(--primary-600, #2563eb);
	}

	.result-status.completed {
		background: var(--success-50, #f0fdf4);
		color: var(--success-600, #16a34a);
	}

	.result-status.cancelled {
		background: var(--gray-100, #f3f4f6);
		color: var(--text-muted, #9ca3af);
	}

	.result-project {
		font-weight: 600;
		color: var(--primary-600, #2563eb);
	}

	.result-due {
		color: var(--text-muted, #9ca3af);
	}

	@media (max-width: 768px) {
		.search-backdrop {
			padding-top: 5vh;
			padding-left: 1rem;
			padding-right: 1rem;
		}
	}
</style>
