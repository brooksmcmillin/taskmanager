<script lang="ts">
	import { goto } from '$app/navigation';
	import { browser } from '$app/environment';
	import { page } from '$app/stores';
	import { api } from '$lib/api/client';
	import { onMount } from 'svelte';

	let username = '';
	let password = '';
	let error = '';
	let returnTo = '/';

	onMount(() => {
		if (browser) {
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
				// Redirect to return_to if present AND safe, otherwise go to homepage
				goto(returnTo, { replaceState: true });
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
</script>

<svelte:head>
	<title>Login - Task Manager</title>
</svelte:head>

<main class="container" style="max-width: 400px; margin: 2rem auto;">
	<div class="card">
		<h1>Login</h1>

		<form on:submit={handleSubmit}>
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

		{#if error}
			<div class="error-message" style="margin-top: 1rem;">
				{error}
			</div>
		{/if}
	</div>
</main>
