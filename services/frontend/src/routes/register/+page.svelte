<script lang="ts">
	import { goto } from '$app/navigation';

	let username = '';
	let email = '';
	let password = '';
	let error = '';
	let success = '';

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = '';
		success = '';

		try {
			const response = await fetch('/api/auth/register', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				credentials: 'include',
				body: JSON.stringify({ username, email, password })
			});

			const data = await response.json();

			if (response.ok) {
				success = 'Registration successful! Redirecting to login...';
				setTimeout(() => {
					goto('/login');
				}, 2000);
			} else {
				// Handle both old format (data.error = string) and new format (data.error = {code, message})
				const errorMessage =
					typeof data.error === 'object' ? data.error.message : data.error;
				error = errorMessage || 'Registration failed';
			}
		} catch (err) {
			error = 'Network error. Please try again.';
		}
	}
</script>

<svelte:head>
	<title>Register - Task Manager</title>
</svelte:head>

<main class="container" style="max-width: 400px; margin: 2rem auto;">
	<div class="card">
		<h1>Register</h1>

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
					minlength="6"
				/>
				<small>Password must be at least 6 characters long</small>
			</div>

			<button type="submit" class="btn btn-primary">Register</button>
		</form>

		{#if error}
			<div class="error-message" style="margin-top: 1rem;">
				{error}
			</div>
		{/if}

		{#if success}
			<div class="success-message" style="margin-top: 1rem;">
				{success}
			</div>
		{/if}

		<p style="text-align: center; margin-top: 1rem;">
			Already have an account? <a href="/login">Login here</a>
		</p>
	</div>
</main>
