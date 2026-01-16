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

	onMount(async () => {
		if (browser) {
			const params = new URLSearchParams(window.location.search);
			const clientId = params.get('client_id');
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

				user = await response.json();

				// Look up client information
				if (clientId) {
					await loadClient(clientId);
				} else {
					error = 'Missing client_id parameter';
				}
			} catch (err) {
				console.error('Auth check failed:', err);
			}
		}
	});

	async function loadClient(clientId: string) {
		try {
			const response = await fetch(`/api/oauth/clients/${clientId}`, {
				credentials: 'include'
			});

			if (!response.ok) {
				error = 'Invalid client_id';
				return;
			}

			client = await response.json();
		} catch (err) {
			console.error('Error loading client:', err);
			error = 'Failed to load client information';
		}
	}

	async function handleAuthorize(action: 'allow' | 'deny') {
		if (!client) return;

		try {
			const requestBody: any = {
				client_id: client.client_id,
				redirect_uri: redirectUri,
				scope: scopes.join(' '),
				state,
				action
			};

			if (codeChallenge) {
				requestBody.code_challenge = codeChallenge;
				requestBody.code_challenge_method = codeChallengeMethod || 'S256';
			}

			const response = await fetch('/api/oauth/authorize', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify(requestBody)
			});

			if (response.ok) {
				const result = await response.json();
				// Redirect to the redirect_uri with the authorization code or error
				window.location.href = result.redirect_uri;
			} else {
				const data = await response.json();
				error = data.error?.message || 'Authorization failed';
			}
		} catch (err) {
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
	<title>Authorize Application</title>
</svelte:head>

<div class="container">
	<div class="auth-container">
		<div class="card">
			<h1>Authorize Application</h1>

			{#if error}
				<div class="error-message">{error}</div>
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
								By authorizing, you allow this application to access your data with the
								permissions listed above.
							</small>
						</p>
					</div>
				</div>
			{:else}
				<p>Loading...</p>
			{/if}
		</div>
	</div>
</div>

<style>
	.error-message {
		background-color: #fef2f2;
		border: 1px solid #fecaca;
		color: #dc2626;
		padding: 0.75rem 1rem;
		border-radius: 0.5rem;
		margin-bottom: 1rem;
	}

	.client-info {
		margin-bottom: 1.5rem;
	}

	.client-info h2 {
		margin-bottom: 0.5rem;
	}

	.permissions {
		margin-bottom: 1.5rem;
		padding: 1rem;
		background-color: var(--bg-secondary, #f8fafc);
		border-radius: 0.5rem;
	}

	.permissions h3 {
		margin-bottom: 0.75rem;
		font-size: 1rem;
	}

	.scope-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.scope-item {
		padding: 0.5rem 0;
		border-bottom: 1px solid var(--border-color, #e2e8f0);
	}

	.scope-item:last-child {
		border-bottom: none;
	}

	.user-info {
		margin-bottom: 1.5rem;
		padding: 0.75rem 1rem;
		background-color: var(--bg-secondary, #f8fafc);
		border-radius: 0.5rem;
		text-align: center;
	}

	.button-group {
		display: flex;
		gap: 1rem;
		justify-content: center;
	}

	.security-note {
		margin-top: 1.5rem;
		text-align: center;
		color: var(--text-muted, #64748b);
	}

	.auth-container {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: 60vh;
		padding: 2rem;
	}

	.card {
		max-width: 480px;
		width: 100%;
		padding: 2rem;
		background: var(--card-bg, white);
		border-radius: 1rem;
		box-shadow:
			0 4px 6px -1px rgba(0, 0, 0, 0.1),
			0 2px 4px -1px rgba(0, 0, 0, 0.06);
	}

	.card h1 {
		text-align: center;
		margin-bottom: 1.5rem;
	}
</style>
