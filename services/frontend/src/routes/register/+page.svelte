<script lang="ts">
	import { goto } from '$app/navigation';

	let username = '';
	let email = '';
	let password = '';
	let error = '';
	let fieldErrors = {
		username: '',
		email: '',
		password: ''
	};
	let touched = {
		username: false,
		email: false,
		password: false
	};

	function validateUsername(): string {
		if (!username.trim()) {
			return 'Username is required';
		}
		if (username.length < 3) {
			return 'Username must be at least 3 characters';
		}
		return '';
	}

	function validateEmail(): string {
		if (!email.trim()) {
			return 'Email is required';
		}
		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		if (!emailRegex.test(email)) {
			return 'Please enter a valid email address';
		}
		return '';
	}

	function validatePassword(): string {
		if (!password) {
			return 'Password is required';
		}

		// Check password strength: must contain at least 2 of: lowercase, uppercase, numbers, special chars
		const hasLower = /[a-z]/.test(password);
		const hasUpper = /[A-Z]/.test(password);
		const hasNumber = /[0-9]/.test(password);
		const hasSpecial = /[^a-zA-Z0-9]/.test(password);
		const categoryCount = [hasLower, hasUpper, hasNumber, hasSpecial].filter(Boolean).length;

		if (categoryCount < 2) {
			return 'Password must contain at least 2 of: lowercase, uppercase, numbers, special chars';
		}

		if (password.length < 6) {
			return 'Password must be at least 6 characters';
		}

		return '';
	}

	function validateField(field: 'username' | 'email' | 'password') {
		touched[field] = true;
		if (field === 'username') {
			fieldErrors.username = validateUsername();
		} else if (field === 'email') {
			fieldErrors.email = validateEmail();
		} else if (field === 'password') {
			fieldErrors.password = validatePassword();
		}
	}

	function validateAllFields(): boolean {
		fieldErrors.username = validateUsername();
		fieldErrors.email = validateEmail();
		fieldErrors.password = validatePassword();
		touched.username = true;
		touched.email = true;
		touched.password = true;

		return !fieldErrors.username && !fieldErrors.email && !fieldErrors.password;
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = '';

		// Validate all fields
		if (!validateAllFields()) {
			return;
		}

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
			console.log('Registration response:', { status: response.status, data });

			if (response.ok) {
				// Redirect immediately to login page
				await goto('/login');
			} else {
				// Handle both old format (data.error = string) and new format (data.error = {code, message})
				const errorMessage = typeof data.error === 'object' ? data.error.message : data.error;
				// Also check for detail field (FastAPI validation errors)
				const detailMessage = data.detail
					? typeof data.detail === 'string'
						? data.detail
						: JSON.stringify(data.detail)
					: null;
				error = errorMessage || detailMessage || 'Registration failed';
			}
		} catch (err) {
			console.error('Registration error:', err);
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

		<form on:submit={handleSubmit} novalidate>
			<div class="form-group">
				<label for="username">Username:</label>
				<input
					type="text"
					id="username"
					name="username"
					class="form-input"
					bind:value={username}
					on:blur={() => validateField('username')}
					required
				/>
				{#if touched.username && fieldErrors.username}
					<div
						data-error="username"
						class="field-error"
						style="color: var(--error-color, #e53e3e); font-size: 0.875rem; margin-top: 0.25rem;"
					>
						{fieldErrors.username}
					</div>
				{/if}
			</div>

			<div class="form-group">
				<label for="email">Email:</label>
				<input
					type="email"
					id="email"
					name="email"
					class="form-input"
					bind:value={email}
					on:blur={() => validateField('email')}
					required
				/>
				{#if touched.email && fieldErrors.email}
					<div
						data-error="email"
						class="field-error"
						style="color: var(--error-color, #e53e3e); font-size: 0.875rem; margin-top: 0.25rem;"
					>
						{fieldErrors.email}
					</div>
				{/if}
			</div>

			<div class="form-group">
				<label for="user-credential">Password:</label>
				<input
					type="password"
					id="user-credential"
					name="password"
					class="form-input"
					bind:value={password}
					on:blur={() => validateField('password')}
					required
					minlength="6"
				/>
				{#if touched.password && fieldErrors.password}
					<div
						data-error="password"
						class="field-error"
						style="color: var(--error-color, #e53e3e); font-size: 0.875rem; margin-top: 0.25rem;"
					>
						{fieldErrors.password}
					</div>
				{:else}
					<small>Password must be at least 6 characters long</small>
				{/if}
			</div>

			<button type="submit" class="btn btn-primary">Register</button>
		</form>

		{#if error}
			<div class="error-message" style="margin-top: 1rem;">
				{error}
			</div>
		{/if}

		<p style="text-align: center; margin-top: 1rem;">
			Already have an account? <a href="/login">Login here</a>
		</p>
	</div>
</main>
