<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';

	let client: any = null;
	let scopes: string[] = [];
	let redirectUri = '';
	let state = '';
	let codeChallenge = '';
	let codeChallengeMethod = '';
	let error = '';
	let user: any = null;
	let clientId = '';
	let loading = true;

	onMount(async () => {
		if (browser) {
			const params = new URLSearchParams(window.location.search);
			clientId = params.get('client_id') || '';
			redirectUri = params.get('redirect_uri') || '';
			const scopeParam = params.get('scope') || '';
			state = params.get('state') || '';
			codeChallenge = params.get('code_challenge') || '';
			codeChallengeMethod = params.get('code_challenge_method') || '';

			scopes = scopeParam.split(' ').filter((s) => s);

			// Check if user is authenticated
			try {
				const response = await fetch('/api/auth/me', {
					credentials: 'include'
				});

				if (!response.ok) {
					// Redirect to login with return_to
					const returnTo = encodeURIComponent(window.location.pathname + window.location.search);
					window.location.href = `/login?return_to=${returnTo}`;
					return;
				}

				const authData = await response.json();
				user = authData.data || authData;

				// Look up client information
				if (clientId) {
					await loadClient(clientId);
				} else {
					error = 'Missing client_id parameter';
					loading = false;
				}
			} catch (err) {
				console.error('Auth check failed:', err);
				error = 'Authentication failed. Please try again.';
				loading = false;
			}
		}
	});

	async function loadClient(clientIdParam: string) {
		try {
			const response = await fetch(`/api/oauth/clients/${clientIdParam}`, {
				credentials: 'include'
			});

			if (!response.ok) {
				error = 'Invalid client_id';
				loading = false;
				return;
			}

			const clientData = await response.json();
			client = clientData.data || clientData;
			loading = false;
		} catch (err) {
			console.error('Error loading client:', err);
			error = 'Failed to load client information';
			loading = false;
		}
	}

	async function handleAuthorize(action: 'allow' | 'deny') {
		if (!client) return;

		try {
			// Use FormData for backend compatibility
			const formData = new FormData();
			formData.append('client_id', clientId);
			formData.append('redirect_uri', redirectUri);
			formData.append('scope', scopes.join(' '));
			formData.append('state', state);
			formData.append('action', action);

			if (codeChallenge) {
				formData.append('code_challenge', codeChallenge);
				formData.append('code_challenge_method', codeChallengeMethod || 'S256');
			}

			const response = await fetch('/api/oauth/authorize', {
				method: 'POST',
				credentials: 'include',
				body: formData
			});

			// Backend returns a redirect response, so we follow it
			if (response.redirected) {
				window.location.href = response.url;
			} else if (response.ok) {
				// If not redirected, try to get redirect URL from body
				const contentType = response.headers.get('content-type');
				if (contentType && contentType.includes('application/json')) {
					const result = await response.json();
					if (result.redirect_uri) {
						window.location.href = result.redirect_uri;
					}
				}
			} else {
				const data = await response.json().catch(() => ({}));
				error = data.error?.message || data.detail?.message || 'Authorization failed';
			}
		} catch (err) {
			console.error('Authorization error:', err);
			error = 'An error occurred. Please try again.';
		}
	}

	function getScopeDescription(scope: string): string {
		switch (scope) {
			case 'read':
				return '📖 Read your todos and projects';
			case 'write':
				return '✏️ Create and modify your todos and projects';
			case 'delete':
				return '🗑️ Delete your todos and projects';
			default:
				return scope;
		}
	}
</script>

<svelte:head>
	<title>Authorize Application - TaskManager</title>
</svelte:head>

<div class="page-container">
	<div class="auth-container">
		<div class="card">
			<h1>Authorize Application</h1>

			{#if error}
				<div class="error-message">{error}</div>
			{:else if loading}
				<div class="loading">
					<p>Loading...</p>
				</div>
			{:else if client}
				<div class="authorization-content">
					<div class="client-info">
						<h2>{client.name}</h2>
						<p>This application is requesting access to your TaskManager account.</p>
					</div>

					<div class="permissions">
						<h3>Requested Permissions:</h3>
						<ul class="scope-list">
							{#each scopes as scope}
								<li class="scope-item">
									{getScopeDescription(scope)}
								</li>
							{/each}
						</ul>
					</div>

					{#if user}
						<div class="user-info">
							<p>
								Signed in as: <strong>{user.username}</strong>
							</p>
						</div>
					{/if}

					<div class="button-group">
						<button on:click={() => handleAuthorize('allow')} class="btn btn-primary">
							Authorize
						</button>
						<button on:click={() => handleAuthorize('deny')} class="btn btn-secondary">
							Deny
						</button>
					</div>

					<div class="security-note">
						<p>
							<small>
								⚠️ Only authorize applications you trust. You can revoke access at any time in your
								account settings.
							</small>
						</p>
					</div>
				</div>
			{/if}
		</div>
	</div>
</div>

<style>
	.page-container {
		min-height: 100vh;
		background-color: var(--bg-page, #f9fafb);
		padding: 2rem 1rem;
	}

	.auth-container {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: calc(100vh - 4rem);
	}

	.card {
		max-width: 480px;
		width: 100%;
		padding: 2rem;
		background: var(--bg-card, white);
		border-radius: var(--radius-xl, 1rem);
		box-shadow: var(--shadow-lg);
		border: 1px solid var(--border-light, #f3f4f6);
	}

	.card h1 {
		text-align: center;
		margin-bottom: 1.5rem;
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--text-primary, #111827);
	}

	.loading {
		text-align: center;
		padding: 2rem;
		color: var(--text-secondary, #6b7280);
	}

	.error-message {
		background-color: var(--error-50, #fef2f2);
		border: 1px solid var(--error-100, #fecaca);
		color: var(--error-600, #dc2626);
		padding: 0.75rem 1rem;
		border-radius: var(--radius-md, 0.5rem);
		margin-bottom: 1rem;
		font-size: 0.875rem;
	}

	.authorization-content {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.client-info h2 {
		margin: 0 0 0.5rem 0;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text-primary, #111827);
	}

	.client-info p {
		margin: 0;
		color: var(--text-secondary, #6b7280);
		font-size: 0.9375rem;
	}

	.permissions {
		padding: 1rem;
		background-color: var(--bg-secondary, #f8fafc);
		border-radius: var(--radius-md, 0.5rem);
		border: 1px solid var(--border-light, #f3f4f6);
	}

	.permissions h3 {
		margin: 0 0 0.75rem 0;
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--text-primary, #111827);
	}

	.scope-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.scope-item {
		padding: 0.625rem 0;
		border-bottom: 1px solid var(--border-light, #e5e7eb);
		color: var(--text-secondary, #4b5563);
		font-size: 0.9375rem;
	}

	.scope-item:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.user-info {
		padding: 0.875rem 1rem;
		background-color: var(--primary-50, #eff6ff);
		border-radius: var(--radius-md, 0.5rem);
		text-align: center;
		border: 1px solid var(--primary-100, #dbeafe);
	}

	.user-info p {
		margin: 0;
		color: var(--text-secondary, #4b5563);
		font-size: 0.9375rem;
	}

	.user-info strong {
		color: var(--primary-700, #1d4ed8);
		font-weight: 600;
	}

	.button-group {
		display: flex;
		gap: 0.75rem;
		justify-content: center;
		margin-top: 0.5rem;
	}

	.btn {
		padding: 0.625rem 1.5rem;
		border-radius: var(--radius-md, 0.5rem);
		font-size: 0.9375rem;
		font-weight: 600;
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
		font-family: inherit;
	}

	.btn-primary {
		background-color: var(--primary-600, #2563eb);
		color: white;
	}

	.btn-primary:hover {
		background-color: var(--primary-700, #1d4ed8);
		transform: translateY(-1px);
		box-shadow: var(--shadow-md);
	}

	.btn-primary:active {
		transform: translateY(0);
	}

	.btn-secondary {
		background-color: var(--gray-200, #e5e7eb);
		color: var(--gray-700, #374151);
	}

	.btn-secondary:hover {
		background-color: var(--gray-300, #d1d5db);
	}

	.security-note {
		text-align: center;
		color: var(--text-muted, #6b7280);
	}

	.security-note p {
		margin: 0;
	}

	.security-note small {
		font-size: 0.8125rem;
		line-height: 1.4;
	}
</style>
