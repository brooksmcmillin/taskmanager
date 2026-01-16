<script lang="ts">
	import { onMount } from 'svelte';
	import Modal from '$lib/components/Modal.svelte';
	import type { OAuthClient } from '$lib/types';

	let clients: OAuthClient[] = [];
	let showModal = false;
	let isEditMode = false;
	let editingClientId: string | null = null;

	// Form fields
	let clientName = '';
	let redirectUris = '';
	let scopes = 'read';
	let grantTypes = 'authorization_code';
	let useCustomCredential = false;
	let clientCredential = '';

	// Credentials display
	let showCredentials = false;
	let displayClientId = '';
	let displayClientSecret = '';

	onMount(async () => {
		await loadClients();
	});

	async function loadClients() {
		try {
			const response = await fetch('/api/oauth/clients', {
				credentials: 'include'
			});

			if (!response.ok) {
				if (response.status === 401) {
					window.location.href = '/login';
					return;
				}
				throw new Error('Failed to load OAuth clients');
			}

			clients = await response.json();
		} catch (error) {
			console.error('Failed to load OAuth clients:', error);
		}
	}

	function openAddModal() {
		isEditMode = false;
		editingClientId = null;
		clientName = '';
		redirectUris = '';
		scopes = 'read';
		grantTypes = 'authorization_code';
		useCustomCredential = false;
		clientCredential = '';
		showCredentials = false;
		showModal = true;
	}

	async function openEditModal(clientId: string) {
		const client = clients.find((c) => c.client_id === clientId);
		if (!client) return;

		isEditMode = true;
		editingClientId = clientId;
		clientName = client.name;
		redirectUris = JSON.parse(client.redirect_uris).join('\n');
		scopes = JSON.parse(client.scopes).join(', ');
		grantTypes = JSON.parse(client.grant_types).join(', ');
		useCustomCredential = false;
		clientCredential = '';
		showCredentials = false;
		showModal = true;
	}

	async function deleteClient(clientId: string, name: string) {
		if (
			!confirm(
				`Are you sure you want to delete "${name}"?\n\nThis will revoke all active tokens for this client and cannot be undone.`
			)
		) {
			return;
		}

		try {
			const response = await fetch(`/api/oauth/clients/${clientId}`, {
				method: 'DELETE',
				credentials: 'include'
			});

			if (response.ok) {
				await loadClients();
			} else if (response.status === 401) {
				window.location.href = '/login';
			} else {
				const error = await response.json();
				alert('Failed to delete client: ' + (error.message || 'Unknown error'));
			}
		} catch (error) {
			alert('Error: ' + (error as Error).message);
		}
	}

	async function handleSubmit() {
		const name = clientName.trim();
		const urisText = redirectUris.trim();
		const scopesText = scopes.trim();
		const grantTypesText = grantTypes.trim();

		// Parse inputs
		const uris = urisText
			.split('\n')
			.map((uri) => uri.trim())
			.filter((uri) => uri);
		const scopesList = scopesText
			.split(',')
			.map((s) => s.trim())
			.filter((s) => s);
		const grantTypesList = grantTypesText
			.split(',')
			.map((g) => g.trim())
			.filter((g) => g);

		if (uris.length === 0) {
			alert('Please provide at least one redirect URI');
			return;
		}

		// Validate custom credential if provided
		if (useCustomCredential && clientCredential && clientCredential.length < 11) {
			alert('Custom client secret must be at least 16 characters');
			return;
		}

		try {
			let response;

			if (isEditMode && editingClientId) {
				// Update existing client
				response = await fetch(`/api/oauth/clients/${editingClientId}`, {
					method: 'PUT',
					headers: { 'Content-Type': 'application/json' },
					credentials: 'include',
					body: JSON.stringify({
						name,
						redirectUris: uris,
						scopes: scopesList,
						grantTypes: grantTypesList
					})
				});
			} else {
				// Create new client
				const requestBody: any = {
					name,
					redirectUris: uris,
					scopes: scopesList,
					grantTypes: grantTypesList
				};

				if (useCustomCredential && clientCredential) {
					requestBody.clientSecret = clientCredential;
				}

				response = await fetch('/api/oauth/clients', {
					method: 'POST',
					headers: { 'Content-Type': 'application/json' },
					credentials: 'include',
					body: JSON.stringify(requestBody)
				});
			}

			if (response.ok) {
				const result = await response.json();

				if (!isEditMode && result.client_secret) {
					// Show credentials for new client
					displayClientId = result.client_id;
					displayClientSecret = result.client_secret;
					showCredentials = true;
				} else {
					// Just close and reload for edits
					showModal = false;
					await loadClients();
				}
			} else if (response.status === 401) {
				window.location.href = '/login';
			} else {
				const error = await response.json();
				alert('Failed to save client: ' + (error.message || 'Unknown error'));
			}
		} catch (error) {
			alert('Error: ' + (error as Error).message);
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
	}

	function closeCredentialsAndReload() {
		showModal = false;
		showCredentials = false;
		loadClients();
	}
</script>

<svelte:head>
	<title>OAuth Clients</title>
</svelte:head>

<main class="container py-8">
	<div class="max-w-6xl mx-auto">
		<div class="flex justify-between items-center mb-8">
			<h1 class="text-3xl font-bold text-gray-900">OAuth Clients</h1>
			<button on:click={openAddModal} class="btn btn-primary"> + Add Client </button>
		</div>

		<!-- Clients List -->
		<div class="space-y-4">
			{#if clients.length === 0}
				<div class="text-center py-12">
					<p class="text-gray-500 mb-4">No OAuth clients yet.</p>
					<p class="text-sm text-gray-400">
						Create your first client to get started with OAuth authentication.
					</p>
				</div>
			{:else}
				{#each clients as client}
					{@const redirectUris = JSON.parse(client.redirect_uris)}
					{@const scopesList = JSON.parse(client.scopes)}
					{@const grantTypesList = JSON.parse(client.grant_types)}
					<div class="client-card">
						<div class="flex justify-between items-start mb-4">
							<div>
								<h3 class="font-semibold text-lg text-gray-800">{client.name}</h3>
								<p class="text-xs text-gray-500 font-mono mt-1">Client ID: {client.client_id}</p>
							</div>
							<div class="flex space-x-2">
								<button on:click={() => openEditModal(client.client_id)} class="btn btn-secondary btn-sm">
									Edit
								</button>
								<button on:click={() => deleteClient(client.client_id, client.name)} class="btn btn-sm bg-red-600 hover:bg-red-700 text-white">
									Delete
								</button>
							</div>
						</div>

						<div class="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
							<div>
								<p class="text-gray-600 font-medium mb-1">Redirect URIs:</p>
								<ul class="list-disc list-inside text-gray-700 space-y-1">
									{#each redirectUris as uri}
										<li class="truncate" title={uri}>{uri}</li>
									{/each}
								</ul>
							</div>
							<div>
								<p class="text-gray-600 font-medium mb-1">Scopes:</p>
								<p class="text-gray-700">{scopesList.join(', ')}</p>
								<p class="text-gray-600 font-medium mb-1 mt-2">Grant Types:</p>
								<p class="text-gray-700">{grantTypesList.join(', ')}</p>
							</div>
						</div>

						<div class="mt-4 pt-4 border-t border-gray-200">
							<div class="flex justify-between items-center text-xs text-gray-500">
								<span>Created: {new Date(client.created_at).toLocaleDateString()}</span>
								<span class="px-2 py-1 rounded {client.is_active ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
									{client.is_active ? 'Active' : 'Inactive'}
								</span>
							</div>
						</div>
					</div>
				{/each}
			{/if}
		</div>
	</div>
</main>

<!-- Add/Edit Modal -->
<Modal bind:show={showModal} title={isEditMode ? 'Edit OAuth Client' : 'Add OAuth Client'}>
	{#if !showCredentials}
		<form on:submit|preventDefault={handleSubmit} class="space-y-4">
			<div>
				<label for="client-name" class="block text-sm font-medium text-gray-700 mb-1">
					Client Name *
				</label>
				<input
					type="text"
					id="client-name"
					bind:value={clientName}
					required
					class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
					placeholder="My Application"
				/>
			</div>

			<div>
				<label for="redirect-uris" class="block text-sm font-medium text-gray-700 mb-1">
					Redirect URIs * (one per line)
				</label>
				<textarea
					id="redirect-uris"
					bind:value={redirectUris}
					required
					rows="3"
					class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
					placeholder={'https://example.com/callback\nhttp://localhost:3000/callback'}
				/>
				<p class="text-xs text-gray-500 mt-1">Enter one URI per line</p>
			</div>

			<div>
				<label for="scopes" class="block text-sm font-medium text-gray-700 mb-1">
					Scopes (comma-separated)
				</label>
				<input
					type="text"
					id="scopes"
					bind:value={scopes}
					class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
					placeholder="read, write"
				/>
			</div>

			<div>
				<label for="grant-types" class="block text-sm font-medium text-gray-700 mb-1">
					Grant Types (comma-separated)
				</label>
				<input
					type="text"
					id="grant-types"
					bind:value={grantTypes}
					class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
					placeholder="authorization_code, refresh_token, device_code"
				/>
				<p class="text-xs text-gray-500 mt-1">
					Available: authorization_code, refresh_token, client_credentials, device_code
				</p>
			</div>

			{#if !isEditMode}
				<div class="border-t border-gray-200 pt-4">
					<div class="flex items-center mb-3">
						<input
							type="checkbox"
							id="use-custom-credential"
							bind:checked={useCustomCredential}
							class="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
						/>
						<label for="use-custom-credential" class="text-sm font-medium text-gray-700">
							Provide custom client secret (optional)
						</label>
					</div>

					{#if useCustomCredential}
						<div>
							<label for="client-credential" class="block text-sm font-medium text-gray-700 mb-1">
								Client Secret
							</label>
							<input
								type="password"
								id="client-credential"
								bind:value={clientCredential}
								class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
								placeholder="Minimum 16 characters"
								minlength="11"
							/>
							<p class="text-xs text-gray-500 mt-1">
								Leave empty to generate a random secret. Must be at least 16 characters if provided.
							</p>
						</div>
					{/if}
				</div>
			{/if}

			<div class="flex justify-end space-x-3 pt-4">
				<button type="button" on:click={() => (showModal = false)} class="btn btn-secondary">
					Cancel
				</button>
				<button type="submit" class="btn btn-primary"> Save Client </button>
			</div>
		</form>
	{:else}
		<!-- New Client Credentials Display -->
		<div class="p-4 bg-yellow-50 border border-yellow-200 rounded-md">
			<h3 class="font-bold text-lg mb-2 text-yellow-800">Client Credentials Created!</h3>
			<p class="text-sm text-yellow-700 mb-3">
				Save these credentials now. The client secret will not be shown again.
			</p>

			<div class="space-y-3">
				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Client ID</label>
					<div class="flex items-center space-x-2">
						<input
							type="text"
							value={displayClientId}
							readonly
							class="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-mono"
						/>
						<button
							type="button"
							on:click={() => copyToClipboard(displayClientId)}
							class="btn btn-sm btn-secondary"
						>
							Copy
						</button>
					</div>
				</div>

				<div>
					<label class="block text-xs font-medium text-gray-700 mb-1">Client Secret</label>
					<div class="flex items-center space-x-2">
						<input
							type="text"
							value={displayClientSecret}
							readonly
							class="flex-1 px-3 py-2 bg-white border border-gray-300 rounded-md text-sm font-mono"
						/>
						<button
							type="button"
							on:click={() => copyToClipboard(displayClientSecret)}
							class="btn btn-sm btn-secondary"
						>
							Copy
						</button>
					</div>
				</div>
			</div>

			<button type="button" on:click={closeCredentialsAndReload} class="mt-4 btn btn-primary w-full">
				Done
			</button>
		</div>
	{/if}
</Modal>
