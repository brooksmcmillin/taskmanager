<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';

	let userCodeParam = '';
	let userCode = '';
	let deviceAuth: any = null;
	let error = '';
	let user: any = null;

	onMount(async () => {
		if (browser) {
			const params = new URLSearchParams(window.location.search);
			// Accept both 'code' and 'user_code' parameters for compatibility
			userCodeParam = params.get('code') || params.get('user_code') || '';
			userCode = userCodeParam;

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

				// If user_code was provided, look it up
				if (userCodeParam) {
					await lookupDeviceAuth(userCodeParam);
				}
			} catch (err) {
				console.error('Auth check failed:', err);
			}
		}
	});

	async function lookupDeviceAuth(code: string) {
		try {
			const response = await fetch(
				`/api/oauth/device/lookup?user_code=${encodeURIComponent(code)}`,
				{
					credentials: 'include'
				}
			);

			if (!response.ok) {
				error = 'Invalid or expired code. Please check the code and try again.';
				deviceAuth = null;
				return;
			}

			deviceAuth = await response.json();
			error = '';
		} catch (err) {
			console.error('Error looking up device code:', err);
			error = 'An error occurred. Please try again.';
			deviceAuth = null;
		}
	}

	function handleCodeSubmit(e: Event) {
		e.preventDefault();
		const code = userCode.trim();
		if (code) {
			// Redirect to same page with user_code parameter
			window.location.href = `/oauth/device?user_code=${encodeURIComponent(code)}`;
		}
	}

	async function handleAuthorize(action: 'allow' | 'deny') {
		if (!deviceAuth) return;

		try {
			const response = await fetch('/api/oauth/device/authorize', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				credentials: 'include',
				body: JSON.stringify({
					user_code: deviceAuth.user_code,
					action
				})
			});

			if (response.ok) {
				if (action === 'allow') {
					window.location.href = '/oauth/device/success';
				} else {
					window.location.href = '/oauth/device/denied';
				}
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

	$: scopes = deviceAuth ? JSON.parse(deviceAuth.scopes) : [];
</script>

<svelte:head>
	<title>Authorize Device</title>
</svelte:head>

<div class="page-container">
	<div class="auth-container">
		<div class="card">
			<h1>Authorize Device</h1>

			{#if !deviceAuth}
				<div class="code-entry">
					<p>Enter the code displayed on your device to authorize it.</p>

					{#if error}
						<div class="error-message">{error}</div>
					{/if}

					<form on:submit={handleCodeSubmit} class="code-form">
						<div class="form-group">
							<label for="user_code">Device Code</label>
							<input
								type="text"
								id="user_code"
								name="user_code"
								placeholder="XXXX-XXXX"
								bind:value={userCode}
								class="code-input"
								maxlength="9"
								pattern="[A-Za-z]{'{4}'}-?[A-Za-z]{'{4}'}"
								required
								autofocus
							/>
							<small>The code is case-insensitive</small>
						</div>
						<button type="submit" class="btn btn-primary"> Continue </button>
					</form>
				</div>
			{:else}
				<div class="authorization-content">
					<div class="client-info">
						<h2>{deviceAuth.client_name}</h2>
						<p>This application is requesting access to your TaskManager account via a device.</p>
					</div>

					<div class="code-display">
						<p>
							Code: <strong class="user-code">{deviceAuth.user_code}</strong>
						</p>
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
							Authorize Device
						</button>
						<button on:click={() => handleAuthorize('deny')} class="btn btn-secondary">
							Deny
						</button>
					</div>

					<div class="security-note">
						<p>
							<small>
								⚠️ Only authorize devices you trust. The device will have access to your account
								until you revoke it.
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
		max-width: 480px;
		width: 100%;
		padding: 2rem;
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

	.code-entry {
		text-align: center;
	}

	.code-entry > p {
		color: var(--text-secondary, #57534e);
		font-size: 0.9375rem;
	}

	.code-form {
		margin-top: 1.5rem;
	}

	.form-group {
		margin-bottom: 1rem;
		text-align: left;
	}

	.form-group label {
		display: block;
		margin-bottom: 0.5rem;
		font-weight: 500;
		color: var(--text-primary, #1c1917);
		font-size: 0.875rem;
	}

	.code-input {
		width: 100%;
		padding: 1rem;
		font-size: 1.5rem;
		font-family: var(--font-mono, 'SF Mono', Monaco, Inconsolata, monospace);
		text-align: center;
		text-transform: uppercase;
		letter-spacing: 0.2em;
		border: 2px solid var(--border-color, #e7e3de);
		border-radius: var(--radius-md, 0.625rem);
		background: var(--bg-input, #ffffff);
	}

	.code-input:focus {
		outline: none;
		border-color: var(--primary-600, #c05621);
		box-shadow: 0 0 0 3px rgba(192, 86, 33, 0.1);
	}

	.form-group small {
		display: block;
		margin-top: 0.5rem;
		color: var(--text-muted, #78716c);
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

	.code-display {
		background-color: var(--bg-secondary, #f7f4f0);
		padding: 0.75rem 1rem;
		border-radius: var(--radius-md, 0.625rem);
		text-align: center;
		border: 1px solid var(--border-light, #f3f0ec);
	}

	.code-display p {
		color: var(--text-secondary, #57534e);
	}

	.user-code {
		font-family: var(--font-mono, 'SF Mono', Monaco, Inconsolata, monospace);
		font-size: 1.25rem;
		letter-spacing: 0.1em;
		color: var(--text-primary, #1c1917);
	}

	.client-info h2 {
		margin-bottom: 0.5rem;
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text-primary, #1c1917);
	}

	.client-info p {
		color: var(--text-secondary, #57534e);
		font-size: 0.9375rem;
	}

	.permissions {
		padding: 1rem;
		background-color: var(--bg-secondary, #f7f4f0);
		border-radius: var(--radius-md, 0.625rem);
		border: 1px solid var(--border-light, #f3f0ec);
	}

	.permissions h3 {
		margin-bottom: 0.75rem;
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
		padding: 0.875rem 1rem;
		background-color: var(--primary-50, #fff5ee);
		border-radius: var(--radius-md, 0.625rem);
		text-align: center;
		border: 1px solid var(--primary-100, #ffe4cc);
	}

	.user-info p {
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
	}

	.btn {
		padding: 0.625rem 1.5rem;
		border-radius: var(--radius-md, 0.625rem);
		font-size: 0.9375rem;
		font-weight: 600;
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
		font-family: inherit;
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
