<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { PUBLIC_REGISTRATION_CODE_REQUIRED } from '$env/static/public';
	import { onMount } from 'svelte';

	// Check if registration code is required (default to true if not set)
	const registrationCodeRequired = PUBLIC_REGISTRATION_CODE_REQUIRED !== 'false';

	let email = '';
	let password = '';
	let registrationCode = '';
	let error = '';
	let fieldErrors = {
		email: '',
		password: '',
		registrationCode: ''
	};
	let touched = {
		email: false,
		password: false,
		registrationCode: false
	};
	let githubEnabled = false;
	let githubLoading = false;

	onMount(async () => {
		if (browser) {
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

	function validateRegistrationCode(): string {
		if (registrationCodeRequired && !registrationCode.trim()) {
			return 'Registration code is required';
		}
		return '';
	}

	function validateField(field: 'email' | 'password' | 'registrationCode') {
		touched[field] = true;
		if (field === 'email') {
			fieldErrors.email = validateEmail();
		} else if (field === 'password') {
			fieldErrors.password = validatePassword();
		} else if (field === 'registrationCode') {
			fieldErrors.registrationCode = validateRegistrationCode();
		}
	}

	function validateAllFields(): boolean {
		fieldErrors.email = validateEmail();
		fieldErrors.password = validatePassword();
		fieldErrors.registrationCode = validateRegistrationCode();
		touched.email = true;
		touched.password = true;
		touched.registrationCode = true;

		return !fieldErrors.email && !fieldErrors.password && !fieldErrors.registrationCode;
	}

	async function handleSubmit(e: Event) {
		e.preventDefault();
		error = '';

		// Validate all fields
		if (!validateAllFields()) {
			return;
		}

		try {
			// Build request body - only include registration_code if required or provided
			const requestBody: any = { email, password };
			if (registrationCodeRequired || registrationCode.trim()) {
				requestBody.registration_code = registrationCode;
			}

			const response = await fetch('/api/auth/register', {
				method: 'POST',
				headers: {
					'Content-Type': 'application/json'
				},
				credentials: 'include',
				body: JSON.stringify(requestBody)
			});

			const data = await response.json();

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

	function handleGitHubSignup() {
		githubLoading = true;
		// Redirect to dashboard after GitHub signup
		window.location.href = '/api/auth/github/authorize?return_to=/';
	}
</script>

<svelte:head>
	<title>Register - Task Manager</title>
</svelte:head>

<main class="container" style="max-width: 400px; margin: 2rem auto;">
	<div class="card">
		<h1>Register</h1>

		{#if githubEnabled}
			<button
				type="button"
				class="btn btn-github"
				on:click={handleGitHubSignup}
				disabled={githubLoading}
			>
				<svg class="github-icon" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
					<path
						fill="currentColor"
						d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"
					/>
				</svg>
				{githubLoading ? 'Redirecting...' : 'Sign up with GitHub'}
			</button>

			<div class="oauth-divider">
				<span>or register with email</span>
			</div>
		{/if}

		<form on:submit={handleSubmit} novalidate>
			{#if registrationCodeRequired}
				<div class="form-group">
					<label for="registration-code">Registration Code:</label>
					<input
						type="text"
						id="registration-code"
						name="registration_code"
						class="form-input"
						bind:value={registrationCode}
						on:blur={() => validateField('registrationCode')}
						required
						placeholder="Enter your registration code"
					/>
					{#if touched.registrationCode && fieldErrors.registrationCode}
						<div
							data-error="registrationCode"
							class="field-error"
							style="color: var(--error-color, #e53e3e); font-size: 0.875rem; margin-top: 0.25rem;"
						>
							{fieldErrors.registrationCode}
						</div>
					{/if}
				</div>
			{/if}

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

			<button type="submit" class="btn btn-primary" style="margin-left: 0; width: 100%;"
				>Register</button
			>
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

<style>
	.oauth-divider {
		display: flex;
		align-items: center;
		text-align: center;
		margin: 1.5rem 0;
		color: var(--text-muted);
	}

	.oauth-divider::before,
	.oauth-divider::after {
		content: '';
		flex: 1;
		border-bottom: 1px solid var(--border-color);
	}

	.oauth-divider span {
		padding: 0 1rem;
		font-size: 0.875rem;
	}

	.btn-github {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: 0.5rem;
		width: 100%;
		padding: 0.625rem 1rem;
		background-color: #24292e;
		color: white;
		border: none;
		border-radius: var(--radius);
		font-size: 0.875rem;
		font-weight: 500;
		cursor: pointer;
		transition: background-color 0.2s ease;
		margin-left: 0;
	}

	.btn-github:hover:not(:disabled) {
		background-color: #1b1f23;
	}

	.btn-github:disabled {
		opacity: 0.7;
		cursor: not-allowed;
	}

	.github-icon {
		width: 20px;
		height: 20px;
	}

	:global([data-theme='dark']) .btn-github {
		background-color: #f0f0f0;
		color: #24292e;
	}

	:global([data-theme='dark']) .btn-github:hover:not(:disabled) {
		background-color: #e0e0e0;
	}
</style>
