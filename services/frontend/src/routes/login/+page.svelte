<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { api } from '$lib/api/client';
	import { authenticateWithPasskey, isWebAuthnSupported } from '$lib/api/webauthn';
	import { onMount } from 'svelte';

	let username = $state('');
	let password = $state('');
	let error = $state('');
	let returnTo = $state('/');
	let webauthnSupported = $state(false);
	let passkeyLoading = $state(false);

	onMount(() => {
		if (browser) {
			// Check WebAuthn support
			webauthnSupported = isWebAuthnSupported();

			// Get return_to parameter from URL
			const params = new URLSearchParams(window.location.search);
			const returnToParam = params.get('return_to');
			if (returnToParam) {
				returnTo = isLocalUrl(returnToParam) ? returnToParam : '/';
			}
		}
	});

	/**
	 * Validates that a URL is safe for redirection (local URLs only).
	 * Prevents open redirect vulnerabilities.
	 */
	function isLocalUrl(url: string): boolean {
		if (!url) return false;

		// Must start with / but NOT // (which would be protocol-relative)
		if (url.startsWith('/') && !url.startsWith('//')) {
			// Additional check: no backslashes (IE quirk), no control chars
			if (!/[\\<>]/.test(url)) {
				return true;
			}
		}

		// Alternatively, validate against current origin
		try {
			const parsed = new URL(url, window.location.origin);
			return parsed.origin === window.location.origin;
		} catch {
			return false;
		}
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = '';

		try {
			const response = await fetch('/api/auth/login', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				credentials: 'include',
				body: JSON.stringify({ username, password })
			});

			const data = await response.json();

			if (response.ok) {
				// Use full page reload to ensure layout re-runs and fetches user data
				// This is necessary because session cookie is set by the backend
				window.location.href = returnTo;
			} else {
				// Handle FastAPI error format: data.detail.message
				// Also support legacy formats for compatibility
				const errorMessage =
					data.detail?.message ||
					(typeof data.error === 'object' ? data.error.message : data.error) ||
					'Login failed';
				error = errorMessage;
			}
		} catch (err) {
			error = 'Network error. Please try again.';
		}
	}

	async function handlePasskeyLogin() {
		error = '';
		passkeyLoading = true;

		try {
			// Pass username if entered, otherwise use discoverable credentials
			await authenticateWithPasskey(username || undefined);
			// Use full page reload to ensure layout re-runs and fetches user data
			window.location.href = returnTo;
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Passkey authentication failed';
			error = errorMessage;
		} finally {
			passkeyLoading = false;
		}
	}
</script>

<svelte:head>
	<title>Login - Task Manager</title>
</svelte:head>

<main class="container" style="max-width: 400px; margin: 2rem auto;">
	<div class="card">
		<h1>Login</h1>

		<form onsubmit={handleSubmit}>
			<div class="form-group">
				<label for="username">Username:</label>
				<input
					type="text"
					id="username"
					name="username"
					class="form-input"
					bind:value={username}
					required
				/>
			</div>

			<div class="form-group">
				<label for="user-credential">Password:</label>
				<input
					type="password"
					id="user-credential"
					name="password"
					class="form-input"
					bind:value={password}
					required
				/>
			</div>

			<button type="submit" class="btn btn-primary">Login</button>
		</form>

		{#if webauthnSupported}
			<div class="divider">
				<span>or</span>
			</div>

			<button
				type="button"
				class="btn btn-secondary passkey-btn"
				onclick={handlePasskeyLogin}
				disabled={passkeyLoading}
			>
				{#if passkeyLoading}
					Authenticating...
				{:else}
					Sign in with Passkey
				{/if}
			</button>
		{/if}

		{#if error}
			<div class="error-message" style="margin-top: 1rem;">
				{error}
			</div>
		{/if}
	</div>
</main>

<style>
	.divider {
		display: flex;
		align-items: center;
		text-align: center;
		margin: 1.5rem 0;
		color: var(--text-muted, #6b7280);
	}

	.divider::before,
	.divider::after {
		content: '';
		flex: 1;
		border-bottom: 1px solid var(--border-color, #e5e7eb);
	}

	.divider span {
		padding: 0 0.75rem;
		font-size: 0.875rem;
	}

	.passkey-btn {
		width: 100%;
	}
</style>
