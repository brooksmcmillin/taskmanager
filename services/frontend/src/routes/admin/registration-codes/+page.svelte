<script lang="ts">
	import { onMount } from 'svelte';
	import { goto } from '$app/navigation';
	import Modal from '$lib/components/Modal.svelte';
	import type { RegistrationCode } from '$lib/types';

	export let data: { user: { is_admin: boolean } | null };

	let codes: RegistrationCode[] = [];
	let showModal = false;
	let loading = true;
	let error = '';

	// Form fields
	let customCode = '';
	let maxUses = 1;
	let expiresAt = '';
	let useCustomCode = false;

	onMount(async () => {
		// Check if user is admin
		if (!data.user?.is_admin) {
			goto('/');
			return;
		}
		await loadCodes();
	});

	async function loadCodes() {
		loading = true;
		error = '';
		try {
			const response = await fetch('/api/registration-codes', {
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
				throw new Error('Failed to load registration codes');
			}

			const result = await response.json();
			codes = result.data || [];
		} catch (err) {
			error = (err as Error).message;
		} finally {
			loading = false;
		}
	}

	function openAddModal() {
		customCode = '';
		maxUses = 1;
		expiresAt = '';
		useCustomCode = false;
		showModal = true;
	}

	async function handleSubmit() {
		try {
			const body: Record<string, unknown> = {
				max_uses: maxUses
			};

			if (useCustomCode && customCode.trim()) {
				body.code = customCode.trim();
			}

			if (expiresAt) {
				body.expires_at = new Date(expiresAt).toISOString();
			}

			const response = await fetch('/api/registration-codes', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify(body)
			});

			if (response.ok) {
				showModal = false;
				await loadCodes();
			} else if (response.status === 401) {
				goto('/login');
			} else if (response.status === 403) {
				alert('You do not have permission to create registration codes');
			} else {
				const errorData = await response.json();
				alert(
					'Failed to create code: ' +
						(errorData.detail?.message || errorData.error?.message || 'Unknown error')
				);
			}
		} catch (err) {
			alert('Error: ' + (err as Error).message);
		}
	}

	async function deleteCode(codeId: number, codeValue: string) {
		if (
			!confirm(
				`Are you sure you want to delete the registration code "${codeValue}"?\n\nThis action cannot be undone.`
			)
		) {
			return;
		}

		try {
			const response = await fetch(`/api/registration-codes/${codeId}`, {
				method: 'DELETE',
				credentials: 'include'
			});

			if (response.ok) {
				await loadCodes();
			} else if (response.status === 401) {
				goto('/login');
			} else if (response.status === 403) {
				alert('You do not have permission to delete registration codes');
			} else {
				const errorData = await response.json();
				alert(
					'Failed to delete code: ' +
						(errorData.detail?.message || errorData.error?.message || 'Unknown error')
				);
			}
		} catch (err) {
			alert('Error: ' + (err as Error).message);
		}
	}

	async function deactivateCode(codeId: number) {
		try {
			const response = await fetch(`/api/registration-codes/${codeId}/deactivate`, {
				method: 'PATCH',
				credentials: 'include'
			});

			if (response.ok) {
				await loadCodes();
			} else if (response.status === 401) {
				goto('/login');
			} else if (response.status === 403) {
				alert('You do not have permission to deactivate registration codes');
			} else {
				const errorData = await response.json();
				alert(
					'Failed to deactivate code: ' +
						(errorData.detail?.message || errorData.error?.message || 'Unknown error')
				);
			}
		} catch (err) {
			alert('Error: ' + (err as Error).message);
		}
	}

	function copyToClipboard(text: string) {
		navigator.clipboard.writeText(text);
	}

	function formatDate(dateStr: string | null): string {
		if (!dateStr) return 'Never';
		return new Date(dateStr).toLocaleString();
	}

	function isExpired(code: RegistrationCode): boolean {
		if (!code.expires_at) return false;
		return new Date(code.expires_at) < new Date();
	}

	function getCodeStatus(code: RegistrationCode): { text: string; class: string } {
		if (!code.is_active) {
			return { text: 'Inactive', class: 'bg-gray-100 text-gray-800' };
		}
		if (isExpired(code)) {
			return { text: 'Expired', class: 'bg-red-100 text-red-800' };
		}
		if (code.current_uses >= code.max_uses) {
			return { text: 'Exhausted', class: 'bg-yellow-100 text-yellow-800' };
		}
		return { text: 'Active', class: 'bg-green-100 text-green-800' };
	}
</script>

<svelte:head>
	<title>Registration Codes - Admin</title>
</svelte:head>

<main class="container py-8">
	<div class="max-w-6xl mx-auto">
		<div class="flex justify-between items-center mb-8">
			<h1 class="text-2xl font-bold text-gray-900">Registration Codes</h1>
			<button on:click={openAddModal} class="btn btn-primary"> + Create Code </button>
		</div>

		{#if loading}
			<div class="text-center py-12">
				<p class="text-gray-500">Loading...</p>
			</div>
		{:else if error}
			<div class="text-center py-12">
				<p class="text-red-500">{error}</p>
				<button on:click={loadCodes} class="btn btn-secondary mt-4">Retry</button>
			</div>
		{:else if codes.length === 0}
			<div class="text-center py-12">
				<p class="text-gray-500 mb-4">No registration codes yet.</p>
				<p class="text-sm text-gray-400">
					Create a registration code to allow new users to register.
				</p>
			</div>
		{:else}
			<div class="space-y-4">
				{#each codes as code}
					{@const status = getCodeStatus(code)}
					<div class="card p-4">
						<div class="flex justify-between items-start mb-4">
							<div>
								<div class="flex items-center space-x-2">
									<code class="text-lg font-mono bg-gray-100 px-2 py-1 rounded">{code.code}</code>
									<button
										on:click={() => copyToClipboard(code.code)}
										class="btn btn-sm btn-secondary"
										title="Copy code"
									>
										Copy
									</button>
								</div>
								{#if code.created_by_username}
									<p class="text-xs text-gray-500 mt-1">Created by: {code.created_by_username}</p>
								{/if}
							</div>
							<div class="flex space-x-2">
								{#if code.is_active && !isExpired(code) && code.current_uses < code.max_uses}
									<button on:click={() => deactivateCode(code.id)} class="btn btn-sm btn-secondary">
										Deactivate
									</button>
								{/if}
								<button
									on:click={() => deleteCode(code.id, code.code)}
									class="btn btn-sm bg-red-600 hover:bg-red-700 text-white"
								>
									Delete
								</button>
							</div>
						</div>

						<div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
							<div>
								<p class="text-gray-600 font-medium">Uses</p>
								<p class="text-gray-900">{code.current_uses} / {code.max_uses}</p>
							</div>
							<div>
								<p class="text-gray-600 font-medium">Expires</p>
								<p class="text-gray-900">{formatDate(code.expires_at)}</p>
							</div>
							<div>
								<p class="text-gray-600 font-medium">Created</p>
								<p class="text-gray-900">{formatDate(code.created_at)}</p>
							</div>
							<div>
								<p class="text-gray-600 font-medium">Status</p>
								<span class="px-2 py-1 rounded text-xs {status.class}">{status.text}</span>
							</div>
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
</main>

<!-- Create Code Modal -->
<Modal bind:show={showModal} title="Create Registration Code">
	<form on:submit|preventDefault={handleSubmit} class="space-y-4">
		<div class="flex items-center mb-3">
			<input
				type="checkbox"
				id="use-custom-code"
				bind:checked={useCustomCode}
				class="mr-2 h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
			/>
			<label for="use-custom-code" class="text-sm font-medium text-gray-700">
				Use custom code (optional)
			</label>
		</div>

		{#if useCustomCode}
			<div>
				<label for="custom-code" class="block text-sm font-medium text-gray-700 mb-1">
					Custom Code
				</label>
				<input
					type="text"
					id="custom-code"
					bind:value={customCode}
					class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
					placeholder="Enter custom code (min 4 characters)"
					minlength="4"
					maxlength="64"
				/>
				<p class="text-xs text-gray-500 mt-1">
					Leave empty to auto-generate a secure code. Custom codes should be hard to guess.
				</p>
			</div>
		{/if}

		<div>
			<label for="max-uses" class="block text-sm font-medium text-gray-700 mb-1">
				Maximum Uses *
			</label>
			<input
				type="number"
				id="max-uses"
				bind:value={maxUses}
				min="1"
				max="1000"
				required
				class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
			/>
			<p class="text-xs text-gray-500 mt-1">
				How many times this code can be used for registration.
			</p>
		</div>

		<div>
			<label for="expires-at" class="block text-sm font-medium text-gray-700 mb-1">
				Expiration Date (optional)
			</label>
			<input
				type="datetime-local"
				id="expires-at"
				bind:value={expiresAt}
				class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
			/>
			<p class="text-xs text-gray-500 mt-1">Leave empty for no expiration.</p>
		</div>

		<div class="flex justify-end space-x-3 pt-4">
			<button type="button" on:click={() => (showModal = false)} class="btn btn-secondary">
				Cancel
			</button>
			<button type="submit" class="btn btn-primary"> Create Code </button>
		</div>
	</form>
</Modal>
