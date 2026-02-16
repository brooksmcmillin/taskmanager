<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';

	export let data: { user: { is_admin: boolean } | null };

	interface LokiSummary {
		connected: boolean;
		labels: string[];
		label_values: Record<string, string[]>;
		series_count: number;
		error: string | null;
	}

	let summary: LokiSummary | null = null;
	let loading = true;
	let fetchError = '';

	onMount(async () => {
		if (!data.user?.is_admin) {
			goto('/');
			return;
		}
		await loadSummary();
	});

	async function loadSummary() {
		loading = true;
		fetchError = '';
		try {
			const response = await fetch('/api/admin/loki/summary', {
				credentials: 'include'
			});

			if (!response.ok) {
				if (response.status === 401) {
					goto('/login');
					return;
				}
				if (response.status === 403) {
					goto('/');
					return;
				}
				throw new Error('Failed to load Loki summary');
			}

			summary = await response.json();
		} catch (err) {
			fetchError = (err as Error).message;
		} finally {
			loading = false;
		}
	}
</script>

<svelte:head>
	<title>Log Ingestion - Admin</title>
</svelte:head>

<main class="container py-8">
	<div class="max-w-6xl mx-auto">
		<div class="flex justify-between items-center mb-8">
			<h1 class="text-2xl font-bold text-gray-900">Log Ingestion</h1>
			<button on:click={loadSummary} class="btn btn-secondary" disabled={loading}>
				{loading ? 'Refreshing...' : 'Refresh'}
			</button>
		</div>

		{#if loading}
			<div class="text-center py-12">
				<p class="text-gray-500">Loading...</p>
			</div>
		{:else if fetchError}
			<div class="text-center py-12">
				<p class="text-red-500">{fetchError}</p>
				<button on:click={loadSummary} class="btn btn-secondary mt-4">Retry</button>
			</div>
		{:else if summary}
			<!-- Connection Status -->
			<div class="card p-4 mb-6">
				<div class="flex items-center space-x-3">
					<span
						class="inline-block w-3 h-3 rounded-full {summary.connected
							? 'bg-green-500'
							: 'bg-red-500'}"
					></span>
					<span class="font-medium text-gray-900">
						{summary.connected ? 'Connected to Loki' : 'Loki unreachable'}
					</span>
				</div>
				{#if summary.error}
					<p class="text-sm text-red-600 mt-2">{summary.error}</p>
				{/if}
			</div>

			{#if summary.connected}
				<!-- Stats -->
				<div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
					<div class="card p-4">
						<p class="text-sm text-gray-600 font-medium">Active Series</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{summary.series_count}</p>
					</div>
					<div class="card p-4">
						<p class="text-sm text-gray-600 font-medium">Labels</p>
						<p class="text-2xl font-bold text-gray-900 mt-1">{summary.labels.length}</p>
					</div>
				</div>

				<!-- Containers -->
				{#if summary.label_values.container?.length}
					<div class="card p-4 mb-6">
						<h2 class="text-lg font-semibold text-gray-900 mb-3">Containers</h2>
						<div class="space-y-2">
							{#each summary.label_values.container as container}
								<div class="flex items-center space-x-2">
									<span class="inline-block w-2 h-2 rounded-full bg-blue-500"></span>
									<code class="text-sm bg-gray-100 px-2 py-1 rounded">{container}</code>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- Log Streams -->
				{#if summary.label_values.logstream?.length}
					<div class="card p-4 mb-6">
						<h2 class="text-lg font-semibold text-gray-900 mb-3">Log Streams</h2>
						<div class="space-y-2">
							{#each summary.label_values.logstream as stream}
								<div class="flex items-center space-x-2">
									<span class="inline-block w-2 h-2 rounded-full bg-purple-500"></span>
									<code class="text-sm bg-gray-100 px-2 py-1 rounded">{stream}</code>
								</div>
							{/each}
						</div>
					</div>
				{/if}

				<!-- All Labels -->
				<div class="card p-4">
					<h2 class="text-lg font-semibold text-gray-900 mb-3">All Labels</h2>
					<div class="flex flex-wrap gap-2">
						{#each summary.labels as label}
							<span class="text-sm bg-gray-100 px-2 py-1 rounded">{label}</span>
						{/each}
					</div>
				</div>
			{/if}
		{/if}
	</div>
</main>
