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
								Signed in as: <strong>{user.email}</strong>
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
		background-color: var(--bg-page, #faf8f6);
		padding: 2rem 1rem;
	}

	.auth-container {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: calc(100vh - 4rem);
	}

	.card {
		max-width: 600px;
		width: 100%;
		padding: 2.5rem 3rem;
		background: var(--bg-card, #ffffff);
		border-radius: var(--radius-xl, 1.25rem);
		box-shadow: var(--shadow-lg, 0 10px 15px -3px rgb(28 25 23 / 0.07));
		border: 1px solid var(--border-light, #f3f0ec);
	}

	.card h1 {
		text-align: center;
		margin-bottom: 1.5rem;
		font-size: 1.75rem;
		font-weight: 700;
		color: var(--text-primary, #1c1917);
	}

	.loading {
		text-align: center;
		padding: 2rem;
		color: var(--text-secondary, #57534e);
	}

	.error-message {
		background-color: var(--error-50, #fef2f2);
		border: 1px solid var(--error-100, #fecaca);
		color: var(--error-600, #dc2626);
		padding: 0.75rem 1rem;
		border-radius: var(--radius-md, 0.625rem);
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
		color: var(--text-primary, #1c1917);
	}

	.client-info p {
		margin: 0;
		color: var(--text-secondary, #57534e);
		font-size: 0.9375rem;
	}

	.permissions {
		padding: 1.25rem 1.5rem;
		background-color: var(--bg-secondary, #f7f4f0);
		border-radius: var(--radius-md, 0.625rem);
		border: 1px solid var(--border-light, #f3f0ec);
	}

	.permissions h3 {
		margin: 0 0 0.75rem 0;
		font-size: 0.9375rem;
		font-weight: 600;
		color: var(--text-primary, #1c1917);
	}

	.scope-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.scope-item {
		padding: 0.625rem 0;
		border-bottom: 1px solid var(--border-light, #f3f0ec);
		color: var(--text-secondary, #57534e);
		font-size: 0.9375rem;
	}

	.scope-item:last-child {
		border-bottom: none;
		padding-bottom: 0;
	}

	.user-info {
		padding: 1rem 1.5rem;
		background-color: var(--primary-50, #fff5ee);
		border-radius: var(--radius-md, 0.625rem);
		text-align: center;
		border: 1px solid var(--primary-100, #ffe4cc);
	}

	.user-info p {
		margin: 0;
		color: var(--text-secondary, #57534e);
		font-size: 0.9375rem;
	}

	.user-info strong {
		color: var(--primary-700, #9a4419);
		font-weight: 600;
	}

	.button-group {
		display: flex;
		gap: 0.75rem;
		justify-content: center;
		margin-top: 0.5rem;
	}

	.btn {
		padding: 0.75rem 2rem;
		border-radius: var(--radius-md, 0.625rem);
		font-size: 1rem;
		font-weight: 600;
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
		font-family: inherit;
		min-width: 120px;
	}

	.btn-primary {
		background-color: var(--primary-600, #c05621);
		color: white;
	}

	.btn-primary:hover {
		background-color: var(--primary-700, #9a4419);
		transform: translateY(-1px);
		box-shadow: var(--shadow-md);
	}

	.btn-primary:active {
		transform: translateY(0);
	}

	.btn-secondary {
		background-color: var(--gray-200, #e7e3de);
		color: var(--gray-700, #44403c);
	}

	.btn-secondary:hover {
		background-color: var(--gray-300, #d4cfc8);
	}

	.security-note {
		text-align: center;
		color: var(--text-muted, #78716c);
	}

	.security-note p {
		margin: 0;
	}

	.security-note small {
		font-size: 0.8125rem;
		line-height: 1.4;
	}
</style>
