<script lang="ts">
	import { onMount } from 'svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { FeedSource, ApiResponse } from '$lib/types';

	let sources: FeedSource[] = $state([]);
	let loading = $state(true);

	onMount(async () => {
		await loadSources();
	});

	async function loadSources() {
		try {
			loading = true;
			const response = await api.get<ApiResponse<FeedSource[]>>('/api/news/sources');
			console.log('Sources API response:', response);
			if (response.data) {
				sources = response.data;
				console.log('Sources loaded:', sources.length);
			} else {
				console.log('No data field in response');
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
	<div class="mb-6">
		<h1 class="text-3xl font-bold mb-2">Feed Sources</h1>
		<p class="text-gray-600">
			Manage RSS feed sources for AI/LLM security news. Quality scores are automatically adjusted
			based on your article ratings.
		</p>
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
					<p class="text-gray-600">No active feed sources</p>
				</div>
			{:else}
				<div class="space-y-4">
					{#each activeSources as source (source.id)}
						<div class="card p-6 hover:shadow-md transition-shadow">
							<div class="flex justify-between items-start gap-6">
								<div class="flex-1">
									<div class="flex items-center gap-3 mb-3">
										<h3 class="text-lg font-semibold">{source.name}</h3>
										<span
											class="badge badge-sm"
											class:bg-purple-100={source.type === 'paper'}
											class:text-purple-800={source.type === 'paper'}
											class:bg-blue-100={source.type === 'article'}
											class:text-blue-800={source.type === 'article'}
											title="Source type"
										>
											{source.type === 'paper' ? '📄 Paper' : '📰 Article'}
										</span>
										<span
											class="badge badge-sm bg-green-100 text-green-800"
											title="This source is active">Active</span
										>
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

								<button
									onclick={() => toggleSource(source.id, source.is_active)}
									class="btn btn-sm btn-outline btn-error shrink-0"
									title="Deactivate this feed source"
								>
									Deactivate
								</button>
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<!-- Inactive Sources -->
		{#if inactiveSources.length > 0}
			<div>
				<h2 class="text-xl font-semibold mb-4">Inactive Sources ({inactiveSources.length})</h2>
				<div class="space-y-4">
					{#each inactiveSources as source (source.id)}
						<div class="card p-6 bg-gray-50 opacity-75 hover:opacity-100 transition-opacity">
							<div class="flex justify-between items-start gap-6">
								<div class="flex-1">
									<div class="flex items-center gap-3 mb-3">
										<h3 class="text-lg font-semibold text-gray-700">{source.name}</h3>
										<span
											class="badge badge-sm"
											class:bg-purple-100={source.type === 'paper'}
											class:text-purple-800={source.type === 'paper'}
											class:bg-blue-100={source.type === 'article'}
											class:text-blue-800={source.type === 'article'}
											title="Source type"
										>
											{source.type === 'paper' ? '📄 Paper' : '📰 Article'}
										</span>
										<span class="badge badge-sm bg-gray-200 text-gray-700">Inactive</span>
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
											<strong class="min-w-[120px]">Last Fetched:</strong>
											<span>{formatDate(source.last_fetched_at)}</span>
										</div>
									</div>
								</div>

								<button
									onclick={() => toggleSource(source.id, source.is_active)}
									class="btn btn-sm btn-primary shrink-0"
									title="Activate this feed source"
								>
									Activate
								</button>
							</div>
						</div>
					{/each}
				</div>
			</div>
		{/if}
	{/if}
</div>

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
