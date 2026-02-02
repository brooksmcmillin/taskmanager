<script lang="ts">
	import { onMount } from 'svelte';
	import Modal from '$lib/components/Modal.svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { ApiKey, ApiKeyCreateResponse } from '$lib/types';

	const MAX_API_KEYS = 10;

	let apiKeys: ApiKey[] = $state([]);
	let showCreateModal = $state(false);
	let showSecretModal = $state(false);

	// Form fields
	let keyName = $state('');
	let expiresAt = $state('');

	// Created key display
	let createdKey: ApiKeyCreateResponse | null = $state(null);

	// Delete confirmation
	let deleteConfirmId: number | null = $state(null);

	onMount(async () => {
		await loadApiKeys();
	});

	async function loadApiKeys() {
		try {
			const response = await api.get<{ data: ApiKey[] }>('/api/api-keys');
			apiKeys = response.data || [];
		} catch (error) {
			if ((error as any).status === 401) {
				window.location.href = '/login';
				return;
			}
			toasts.show('Failed to load API keys: ' + (error as Error).message, 'error');
		}
	}

	function openCreateModal() {
		keyName = '';
		expiresAt = '';
		showCreateModal = true;
	}

	async function handleCreate() {
		const name = keyName.trim();
		if (!name) {
			toasts.show('Please enter a name for the API key', 'error');
			return;
		}

		try {
			const body: { name: string; expires_at?: string } = { name };
			if (expiresAt) {
				body.expires_at = new Date(expiresAt).toISOString();
			}

			const response = await api.post<{ data: ApiKeyCreateResponse }>('/api/api-keys', body);
			createdKey = response.data;
			showCreateModal = false;
			showSecretModal = true;
			await loadApiKeys();
		} catch (error) {
			if ((error as any).status === 401) {
				window.location.href = '/login';
				return;
			}
			toasts.show(
				'Failed to create API key: ' + ((error as any).detail?.message || (error as Error).message),
				'error'
			);
		}
	}

	async function toggleKeyStatus(key: ApiKey) {
		try {
			if (key.is_active) {
				await api.post(`/api/api-keys/${key.id}/revoke`);
				toasts.show('API key revoked', 'success');
			} else {
				await api.put(`/api/api-keys/${key.id}`, { is_active: true });
				toasts.show('API key activated', 'success');
			}
			await loadApiKeys();
		} catch (error) {
			toasts.show('Failed to update API key: ' + (error as Error).message, 'error');
		}
	}

	async function deleteKey(id: number) {
		try {
			await api.delete(`/api/api-keys/${id}`);
			toasts.show('API key deleted', 'success');
			deleteConfirmId = null;
			await loadApiKeys();
		} catch (error) {
			toasts.show('Failed to delete API key: ' + (error as Error).message, 'error');
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
		toasts.show('Copied to clipboard', 'success');
	}

	function closeSecretModal() {
		showSecretModal = false;
		createdKey = null;
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		return new Date(dateStr).toLocaleDateString();
	}

	function formatDateTime(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		return new Date(dateStr).toLocaleString();
	}

	function isExpired(expiresAt: string | null): boolean {
		if (!expiresAt) return false;
		return new Date(expiresAt) < new Date();
	}
</script>

<svelte:head>
	<title>API Keys</title>
</svelte:head>

<main class="container py-8">
	<div class="max-w-6xl mx-auto">
		<div class="flex justify-between items-center mb-8">
			<div>
				<h1 class="text-2xl font-bold text-gray-900">API Keys</h1>
				<p class="text-sm text-gray-500 mt-1">
					{apiKeys.length} of {MAX_API_KEYS} keys used
				</p>
			</div>
			<button
				onclick={openCreateModal}
				class="btn btn-primary"
				disabled={apiKeys.length >= MAX_API_KEYS}
			>
				+ Create API Key
			</button>
		</div>

		<!-- API Keys List -->
		<div class="space-y-4">
			{#if apiKeys.length === 0}
				<div class="text-center py-12">
					<svg
						class="mx-auto h-12 w-12 text-gray-400"
						fill="none"
						viewBox="0 0 24 24"
						stroke="currentColor"
					>
						<path
							stroke-linecap="round"
							stroke-linejoin="round"
							stroke-width="2"
							d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z"
						/>
					</svg>
					<p class="text-gray-500 mt-4 mb-2">No API keys yet.</p>
					<p class="text-sm text-gray-400">
						Create an API key to access TaskManager programmatically.
					</p>
				</div>
			{:else}
				{#each apiKeys as key}
					<div class="card p-6">
						<div class="flex justify-between items-start mb-4">
							<div>
								<h3 class="font-semibold text-lg">{key.name}</h3>
								<p class="text-xs text-gray-500 font-mono mt-1">
									{key.key_prefix}...
								</p>
							</div>
							<div class="flex items-center space-x-2">
								{#if isExpired(key.expires_at)}
									<span class="px-2 py-1 text-xs rounded bg-gray-100 text-gray-600"> Expired </span>
								{:else}
									<span
										class="px-2 py-1 text-xs rounded {key.is_active
											? 'bg-green-100 text-green-800'
											: 'bg-red-100 text-red-800'}"
									>
										{key.is_active ? 'Active' : 'Revoked'}
									</span>
								{/if}
							</div>
						</div>

						<div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm mb-4">
							<div>
								<p class="text-gray-600 font-medium">Created</p>
								<p class="text-gray-800">{formatDate(key.created_at)}</p>
							</div>
							<div>
								<p class="text-gray-600 font-medium">Expires</p>
								<p class="text-gray-800">{formatDate(key.expires_at)}</p>
							</div>
							<div>
								<p class="text-gray-600 font-medium">Last Used</p>
								<p class="text-gray-800">{formatDateTime(key.last_used_at)}</p>
							</div>
						</div>

						<div class="flex justify-end space-x-2 pt-4 border-t border-gray-200">
							{#if !isExpired(key.expires_at)}
								<button
									onclick={() => toggleKeyStatus(key)}
									class="btn btn-sm {key.is_active ? 'btn-secondary' : 'btn-primary'}"
								>
									{key.is_active ? 'Revoke' : 'Activate'}
								</button>
							{/if}
							{#if deleteConfirmId === key.id}
								<button onclick={() => deleteKey(key.id)} class="btn btn-sm btn-danger">
									Confirm Delete
								</button>
								<button onclick={() => (deleteConfirmId = null)} class="btn btn-sm btn-secondary">
									Cancel
								</button>
							{:else}
								<button onclick={() => (deleteConfirmId = key.id)} class="btn btn-sm btn-danger">
									Delete
								</button>
							{/if}
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</main>

<!-- Create Modal -->
<Modal bind:show={showCreateModal} title="Create API Key">
	<form
		onsubmit={(e) => {
			e.preventDefault();
			handleCreate();
		}}
		class="space-y-4"
	>
		<div>
			<label for="key-name" class="block text-sm font-medium text-gray-700 mb-1">
				Key Name *
			</label>
			<input
				type="text"
				id="key-name"
				bind:value={keyName}
				required
				class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
				placeholder="My API Key"
			/>
			<p class="text-xs text-gray-500 mt-1">A descriptive name to identify this key</p>
		</div>

		<div>
			<label for="expires-at" class="block text-sm font-medium text-gray-700 mb-1">
				Expiration Date (optional)
			</label>
			<input
				type="date"
				id="expires-at"
				bind:value={expiresAt}
				min={new Date().toISOString().split('T')[0]}
				class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
			/>
			<p class="text-xs text-gray-500 mt-1">Leave empty for no expiration</p>
		</div>

		<div class="flex justify-end space-x-3 pt-4">
			<button type="button" onclick={() => (showCreateModal = false)} class="btn btn-secondary">
				Cancel
			</button>
			<button type="submit" class="btn btn-primary"> Create Key </button>
		</div>
	</form>
</Modal>

<!-- Secret Display Modal -->
<Modal bind:show={showSecretModal} title="API Key Created">
	{#if createdKey}
		<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-md">
			<div class="flex items-start mb-3">
				<svg
					class="h-5 w-5 text-yellow-600 mt-0.5 mr-2 flex-shrink-0"
					fill="none"
					viewBox="0 0 24 24"
					stroke="currentColor"
				>
					<path
						stroke-linecap="round"
						stroke-linejoin="round"
						stroke-width="2"
						d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
					/>
				</svg>
				<div>
					<h3 class="font-bold text-yellow-800">Save your API key now!</h3>
					<p class="text-sm text-yellow-700 mt-1">
						This is the only time you'll see this key. Copy and store it securely.
					</p>
				</div>
			</div>

			<div class="space-y-3 mt-4">
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Key Name</label>
					<p class="text-sm font-medium text-gray-900">{createdKey.name}</p>
				</div>

				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">API Key</label>
					<div class="flex items-center space-x-2">
						<input
							type="text"
							value={createdKey.key}
							readonly
							class="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-mono"
						/>
						<button
							type="button"
							onclick={() => copyToClipboard(createdKey!.key)}
							class="btn btn-sm btn-secondary"
						>
							Copy
						</button>
					</div>
				</div>
			</div>

			<button type="button" onclick={closeSecretModal} class="mt-4 btn btn-primary w-full">
				Done
			</button>
		</div>
	{/if}
</Modal>

<style>
	.btn-danger {
		background-color: #dc2626;
		color: white;
	}

	.btn-danger:hover {
		background-color: #b91c1c;
	}
</style>
