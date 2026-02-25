<script lang="ts">
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { api } from '$lib/api/client';
	import { authenticateWithPasskey, isWebAuthnSupported } from '$lib/api/webauthn';
	import { onMount } from 'svelte';

	let email = $state('');
	let password = $state('');
	let error = $state('');
	let returnTo = $state('/');
	let webauthnSupported = $state(false);
	let passkeyLoading = $state(false);
	let githubEnabled = $state(false);
	let githubLoading = $state(false);

	onMount(async () => {
		if (browser) {
			// Check WebAuthn support
			webauthnSupported = isWebAuthnSupported();

			// Get return_to parameter from URL
			const params = new URLSearchParams(window.location.search);
			const returnToParam = params.get('return_to');
			if (returnToParam) {
				returnTo = isLocalUrl(returnToParam) ? returnToParam : '/';
			}

			// Check for OAuth error in URL
			const errorParam = params.get('error');
			if (errorParam) {
				error = errorParam;
			}

			// Check if GitHub OAuth is enabled
			try {
				const response = await fetch('/api/auth/github/config');
				if (response.ok) {
					const config = await response.json();
					githubEnabled = config.enabled;
				}
			} catch {
				// GitHub OAuth not available
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
				body: JSON.stringify({ email, password })
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
			// Pass email if entered, otherwise use discoverable credentials
			await authenticateWithPasskey(email || undefined);
			// Use full page reload to ensure layout re-runs and fetches user data
			window.location.href = returnTo;
		} catch (err) {
			const errorMessage = err instanceof Error ? err.message : 'Passkey authentication failed';
			error = errorMessage;
		} finally {
			passkeyLoading = false;
		}
	}

	function handleGitHubLogin() {
		githubLoading = true;
		const encodedReturnTo = encodeURIComponent(returnTo);
		window.location.href = `/api/auth/github/authorize?return_to=${encodedReturnTo}`;
	}
</script>

<svelte:head>
	<title>Login - Task Manager</title>
</svelte:head>

<main class="auth-page">
	<div class="card auth-card">
		<h1 class="auth-title">Login</h1>

		{#if error}
			<div class="error-message" style="margin-bottom: 1rem;">
				{error}
			</div>
		{/if}

		<form onsubmit={handleSubmit}>
			<div class="form-group">
				<label for="email">Email:</label>
				<input
					type="email"
					id="email"
					name="email"
					class="form-input"
					bind:value={email}
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

			<button type="submit" class="btn btn-primary" style="margin-left: 0; width: 100%;">
				Login
			</button>
		</form>

		{#if webauthnSupported || githubEnabled}
			<div class="auth-divider">
				<span>or</span>
			</div>
		{/if}

		{#if webauthnSupported}
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

		{#if githubEnabled}
			<button
				type="button"
				class="btn btn-github"
				onclick={handleGitHubLogin}
				disabled={githubLoading}
			>
				<svg class="github-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
					<path
						fill="currentColor"
						d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
					/>
				</svg>
				{githubLoading ? 'Redirecting...' : 'Sign in with GitHub'}
			</button>
		{/if}

		<p style="text-align: center; margin-top: 1.5rem;">
			Don't have an account? <a href="/register">Register here</a>
		</p>
	</div>
</main>

<style>
	.passkey-btn {
		width: 100%;
		margin-bottom: 0.75rem;
	}
</style>
