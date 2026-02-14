<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import FeedSourceModal from '$lib/components/FeedSourceModal.svelte';
	import type { FeedSource, ApiResponse } from '$lib/types';

	let sources: FeedSource[] = $state([]);
	let loading = $state(true);
	let showFeaturedOnly = $state(true);
	let sourceModal: FeedSourceModal;

	onMount(async () => {
		await loadSources();
	});

	async function loadSources() {
		try {
			loading = true;
			const params: Record<string, string> = {};
			if (showFeaturedOnly) {
				params.featured = 'true';
			}
			const response = await api.get<ApiResponse<FeedSource[]>>('/api/news/sources', {
				params
			});
			if (response.data) {
				sources = response.data;
			}
		} catch (error) {
			console.error('Error loading sources:', error);
			toasts.show('Failed to load feed sources: ' + (error as Error).message, 'error');
		} finally {
			loading = false;
		}
	}

	async function toggleSource(sourceId: number, isActive: boolean) {
		try {
			await api.post(`/api/news/sources/${sourceId}/toggle`, { is_active: !isActive });

			// Update local state
			sources = sources.map((s) => (s.id === sourceId ? { ...s, is_active: !isActive } : s));

			toasts.show(!isActive ? 'Feed source activated' : 'Feed source deactivated', 'success');
		} catch (error) {
			toasts.show('Failed to toggle feed source: ' + (error as Error).message, 'error');
		}
	}

	async function toggleFilter(featured: boolean) {
		showFeaturedOnly = featured;
		await loadSources();
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		const date = new Date(dateStr);
		return date.toLocaleDateString('en-US', {
			year: 'numeric',
			month: 'short',
			day: 'numeric',
			hour: '2-digit',
			minute: '2-digit'
		});
	}

	function getQualityColor(score: number): string {
		if (score >= 1.5) return 'text-green-600';
		if (score >= 1.0) return 'text-blue-600';
		if (score >= 0.5) return 'text-yellow-600';
		return 'text-red-600';
	}

	function getQualityLabel(score: number): string {
		if (score >= 1.5) return 'Excellent';
		if (score >= 1.0) return 'Good';
		if (score >= 0.5) return 'Fair';
		return 'Poor';
	}

	let activeSources = $derived(sources.filter((s) => s.is_active));
	let inactiveSources = $derived(sources.filter((s) => !s.is_active));
</script>

<div class="container mx-auto p-6">
	<div class="mb-6 flex items-start justify-between">
		<div>
			<h1 class="text-3xl font-bold mb-2">Feed Sources</h1>
			<p class="text-gray-600">
				Manage RSS feed sources for AI/LLM security news. Quality scores are automatically
				adjusted based on your article ratings.
			</p>
		</div>
		<button class="btn btn-primary shrink-0" onclick={() => sourceModal.open()}>
			Add Source
		</button>
	</div>

	<!-- Filter Toggle -->
	<div class="flex gap-1 mb-6 bg-gray-100 rounded-lg p-1 w-fit">
		<button
			class="px-4 py-2 rounded-md text-sm font-medium transition-colors"
			class:bg-white={showFeaturedOnly}
			class:shadow-sm={showFeaturedOnly}
			class:text-gray-900={showFeaturedOnly}
			class:text-gray-600={!showFeaturedOnly}
			onclick={() => toggleFilter(true)}
		>
			Featured
		</button>
		<button
			class="px-4 py-2 rounded-md text-sm font-medium transition-colors"
			class:bg-white={!showFeaturedOnly}
			class:shadow-sm={!showFeaturedOnly}
			class:text-gray-900={!showFeaturedOnly}
			class:text-gray-600={showFeaturedOnly}
			onclick={() => toggleFilter(false)}
		>
			All Sources
		</button>
	</div>

	<!-- Stats -->
	<div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
		<div class="card p-4">
			<div class="text-sm text-gray-600">Total Sources</div>
			<div class="text-2xl font-bold">{sources.length}</div>
		</div>
		<div class="card p-4">
			<div class="text-sm text-gray-600">Active Sources</div>
			<div class="text-2xl font-bold text-green-600">{activeSources.length}</div>
		</div>
		<div class="card p-4">
			<div class="text-sm text-gray-600">Inactive Sources</div>
			<div class="text-2xl font-bold text-gray-400">{inactiveSources.length}</div>
		</div>
	</div>

	{#if loading}
		<div class="text-center py-12">
			<div class="spinner"></div>
			<p class="text-gray-600 mt-2">Loading sources...</p>
		</div>
	{:else}
		<!-- Active Sources -->
		<div class="mb-8">
			<h2 class="text-xl font-semibold mb-4">Active Sources ({activeSources.length})</h2>
			{#if activeSources.length === 0}
				<div class="text-center py-8 bg-gray-50 rounded-lg">
					<p class="text-gray-600">
						{showFeaturedOnly ? 'No featured sources. Switch to "All Sources" or add a new source.' : 'No active feed sources'}
					</p>
				</div>
			{:else}
				<div class="space-y-4">
					{#each activeSources as source (source.id)}
						<div class="card p-6 hover:shadow-md transition-shadow">
							<div class="flex justify-between items-start gap-6">
								<div class="flex-1">
									<div class="flex items-center gap-3 mb-3">
										<button
											class="text-lg font-semibold hover:text-blue-600 transition-colors text-left"
											onclick={() => sourceModal.openEdit(source)}
											title="Edit source"
										>
											{source.name}
										</button>
										<span
											class="badge badge-sm"
											class:bg-purple-100={source.type === 'paper'}
											class:text-purple-800={source.type === 'paper'}
											class:bg-blue-100={source.type === 'article'}
											class:text-blue-800={source.type === 'article'}
											title="Source type"
										>
											{source.type === 'paper' ? 'Paper' : 'Article'}
										</span>
										<span
											class="badge badge-sm bg-green-100 text-green-800"
											title="This source is active">Active</span
										>
										{#if source.is_featured}
											<span
												class="badge badge-sm bg-amber-100 text-amber-800"
												title="Featured source">Featured</span
											>
										{/if}
										<span
											class="badge badge-sm {getQualityColor(source.quality_score)}"
											title="Quality score based on your ratings"
										>
											{getQualityLabel(source.quality_score)} ({source.quality_score.toFixed(2)})
										</span>
									</div>

									{#if source.description}
										<p class="text-gray-600 text-sm mb-4">{source.description}</p>
									{/if}

									<div class="space-y-2 text-sm text-gray-600">
										<div class="flex items-start gap-2">
											<strong class="min-w-[120px]">URL:</strong>
											<a
												href={source.url}
												target="_blank"
												rel="noopener noreferrer"
												class="text-blue-600 hover:underline break-all"
											>
												{source.url}
											</a>
										</div>
										<div class="flex items-center gap-2">
											<strong class="min-w-[120px]">Fetch Interval:</strong>
											<span>Every {source.fetch_interval_hours} hours</span>
										</div>
										<div class="flex items-center gap-2">
											<strong class="min-w-[120px]">Last Fetched:</strong>
											<span>{formatDate(source.last_fetched_at)}</span>
										</div>
									</div>
								</div>

								<div class="flex items-center gap-2 shrink-0">
									<button
										onclick={() => sourceModal.openEdit(source)}
										class="btn btn-sm btn-outline"
										title="Edit source"
									>
										Edit
									</button>
									<button
										onclick={() => toggleSource(source.id, source.is_active)}
										class="btn btn-sm btn-outline btn-error"
										title="Deactivate this feed source"
									>
										Deactivate
									</button>
								</div>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Inactive Sources -->
		{#if inactiveSources.length > 0}
			<div>
				<h2 class="text-xl font-semibold mb-4">
					Inactive Sources ({inactiveSources.length})
				</h2>
				<div class="space-y-4">
					{#each inactiveSources as source (source.id)}
						<div
							class="card p-6 bg-gray-50 opacity-75 hover:opacity-100 transition-opacity"
						>
							<div class="flex justify-between items-start gap-6">
								<div class="flex-1">
									<div class="flex items-center gap-3 mb-3">
										<button
											class="text-lg font-semibold text-gray-700 hover:text-blue-600 transition-colors text-left"
											onclick={() => sourceModal.openEdit(source)}
											title="Edit source"
										>
											{source.name}
										</button>
										<span
											class="badge badge-sm"
											class:bg-purple-100={source.type === 'paper'}
											class:text-purple-800={source.type === 'paper'}
											class:bg-blue-100={source.type === 'article'}
											class:text-blue-800={source.type === 'article'}
											title="Source type"
										>
											{source.type === 'paper' ? 'Paper' : 'Article'}
										</span>
										<span class="badge badge-sm bg-gray-200 text-gray-700"
											>Inactive</span
										>
										{#if source.is_featured}
											<span
												class="badge badge-sm bg-amber-100 text-amber-800"
												title="Featured source">Featured</span
											>
										{/if}
										<span
											class="badge badge-sm {getQualityColor(source.quality_score)}"
											title="Quality score based on your ratings"
										>
											{getQualityLabel(source.quality_score)} ({source.quality_score.toFixed(2)})
										</span>
									</div>

									{#if source.description}
										<p class="text-gray-600 text-sm mb-4">
											{source.description}
										</p>
									{/if}

									<div class="space-y-2 text-sm text-gray-600">
										<div class="flex items-start gap-2">
											<strong class="min-w-[120px]">URL:</strong>
											<a
												href={source.url}
												target="_blank"
												rel="noopener noreferrer"
												class="text-blue-600 hover:underline break-all"
											>
												{source.url}
											</a>
										</div>
										<div class="flex items-center gap-2">
											<strong class="min-w-[120px]">Last Fetched:</strong>
											<span>{formatDate(source.last_fetched_at)}</span>
										</div>
									</div>
								</div>

								<div class="flex items-center gap-2 shrink-0">
									<button
										onclick={() => sourceModal.openEdit(source)}
										class="btn btn-sm btn-outline"
										title="Edit source"
									>
										Edit
									</button>
									<button
										onclick={() => toggleSource(source.id, source.is_active)}
										class="btn btn-sm btn-primary"
										title="Activate this feed source"
									>
										Activate
									</button>
								</div>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>

<FeedSourceModal bind:this={sourceModal} on:success={loadSources} />

<style>
	.spinner {
		width: 48px;
		height: 48px;
		border: 4px solid #f3f4f6;
		border-top: 4px solid #3b82f6;
		border-radius: 50%;
		animation: spin 1s linear infinite;
		margin: 0 auto;
	}

	@keyframes spin {
		0% {
			transform: rotate(0deg);
		}
		100% {
			transform: rotate(360deg);
		}
	}

	.badge {
		@apply px-2 py-1 rounded text-xs font-medium;
	}

	.badge-sm {
		@apply px-1.5 py-0.5 text-xs;
	}
</style>
