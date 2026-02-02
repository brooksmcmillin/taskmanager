<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/stores';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { User } from '$lib/types';

	// Get user from layout data
	let user: User | null = $derived($page.data.user);

	// Email form state
	let newEmail = $state('');
	let emailError = $state('');
	let emailTouched = $state(false);
	let emailSubmitting = $state(false);

	// Password form state
	let currentPassword = $state('');
	let newPassword = $state('');
	let confirmPassword = $state('');
	let passwordErrors = $state({
		currentPassword: '',
		newPassword: '',
		confirmPassword: ''
	});
	let passwordTouched = $state({
		currentPassword: false,
		newPassword: false,
		confirmPassword: false
	});
	let passwordSubmitting = $state(false);

	// Initialize email field with current email
	$effect(() => {
		if (user && !newEmail) {
			newEmail = user.email;
		}
	});

	// Email validation
	function validateEmail(): string {
		if (!newEmail.trim()) {
			return 'Email is required';
		}
		const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
		if (!emailRegex.test(newEmail)) {
			return 'Please enter a valid email address';
		}
		return '';
	}

	function validateEmailField() {
		emailTouched = true;
		emailError = validateEmail();
	}

	// Password validation
	function validateCurrentPassword(): string {
		if (!currentPassword) {
			return 'Current password is required';
		}
		return '';
	}

	function validateNewPassword(): string {
		if (!newPassword) {
			return 'New password is required';
		}
		if (newPassword.length < 8) {
			return 'Password must be at least 8 characters';
		}
		// Check password strength: must contain at least 2 of: lowercase, uppercase, numbers, special chars
		const hasLower = /[a-z]/.test(newPassword);
		const hasUpper = /[A-Z]/.test(newPassword);
		const hasNumber = /[0-9]/.test(newPassword);
		const hasSpecial = /[^a-zA-Z0-9]/.test(newPassword);
		const categoryCount = [hasLower, hasUpper, hasNumber, hasSpecial].filter(Boolean).length;
		if (categoryCount < 2) {
			return 'Password must contain at least 2 of: lowercase, uppercase, numbers, special chars';
		}
		return '';
	}

	function validateConfirmPassword(): string {
		if (!confirmPassword) {
			return 'Please confirm your new password';
		}
		if (confirmPassword !== newPassword) {
			return 'Passwords do not match';
		}
		return '';
	}

	function validatePasswordField(field: 'currentPassword' | 'newPassword' | 'confirmPassword') {
		passwordTouched[field] = true;
		if (field === 'currentPassword') {
			passwordErrors.currentPassword = validateCurrentPassword();
		} else if (field === 'newPassword') {
			passwordErrors.newPassword = validateNewPassword();
			// Also validate confirm password if it's been touched
			if (passwordTouched.confirmPassword) {
				passwordErrors.confirmPassword = validateConfirmPassword();
			}
		} else if (field === 'confirmPassword') {
			passwordErrors.confirmPassword = validateConfirmPassword();
		}
	}

	function validateAllPasswordFields(): boolean {
		passwordErrors.currentPassword = validateCurrentPassword();
		passwordErrors.newPassword = validateNewPassword();
		passwordErrors.confirmPassword = validateConfirmPassword();
		passwordTouched.currentPassword = true;
		passwordTouched.newPassword = true;
		passwordTouched.confirmPassword = true;
		return (
			!passwordErrors.currentPassword &&
			!passwordErrors.newPassword &&
			!passwordErrors.confirmPassword
		);
	}

	// Submit handlers
	async function handleEmailSubmit(e: Event) {
		e.preventDefault();
		emailError = validateEmail();
		emailTouched = true;

		if (emailError) return;

		// Don't submit if email hasn't changed
		if (user && newEmail === user.email) {
			toasts.show('Email is the same as current', 'info');
			return;
		}

		emailSubmitting = true;
		try {
			const response = await api.put<{ message: string; user: User }>('/api/auth/email', {
				email: newEmail
			});
			toasts.show(response.message || 'Email updated successfully', 'success');
			// Reload to update user data in layout
			window.location.reload();
		} catch (error) {
			toasts.show((error as Error).message || 'Failed to update email', 'error');
		} finally {
			emailSubmitting = false;
		}
	}

	async function handlePasswordSubmit(e: Event) {
		e.preventDefault();

		if (!validateAllPasswordFields()) return;

		passwordSubmitting = true;
		try {
			const response = await api.put<{ message: string }>('/api/auth/password', {
				current_password: currentPassword,
				new_password: newPassword
			});
			toasts.show(response.message || 'Password updated successfully. Please log in again.', 'success');
			// Redirect to login since all sessions are invalidated after password change
			setTimeout(() => {
				goto('/login');
			}, 1500);
		} catch (error) {
			toasts.show((error as Error).message || 'Failed to update password', 'error');
			passwordSubmitting = false;
		}
	}
</script>

<svelte:head>
	<title>Settings - Task Manager</title>
</svelte:head>

<main class="container" style="max-width: 600px; margin: 2rem auto;">
	<h1 style="margin-bottom: 2rem;">Settings</h1>

	<!-- Email Update Section -->
	<div class="card" style="margin-bottom: 2rem;">
		<h2>Update Email</h2>
		<p class="text-muted" style="margin-bottom: 1rem;">Change your account email address.</p>

		<form onsubmit={handleEmailSubmit} novalidate>
			<div class="form-group">
				<label for="email">Email Address</label>
				<input
					type="email"
					id="email"
					class="form-input"
					bind:value={newEmail}
					onblur={validateEmailField}
					disabled={emailSubmitting}
					required
				/>
				{#if emailTouched && emailError}
					<div class="field-error">{emailError}</div>
				{/if}
			</div>

			<button type="submit" class="btn btn-primary" disabled={emailSubmitting}>
				{emailSubmitting ? 'Updating...' : 'Update Email'}
			</button>
		</form>
	</div>

	<!-- Password Update Section -->
	<div class="card">
		<h2>Change Password</h2>
		<p class="text-muted" style="margin-bottom: 1rem;">
			Update your password. You'll need to enter your current password first.
		</p>

		<form onsubmit={handlePasswordSubmit} novalidate>
			<div class="form-group">
				<label for="current-password">Current Password</label>
				<input
					type="password"
					id="current-password"
					class="form-input"
					bind:value={currentPassword}
					onblur={() => validatePasswordField('currentPassword')}
					disabled={passwordSubmitting}
					required
				/>
				{#if passwordTouched.currentPassword && passwordErrors.currentPassword}
					<div class="field-error">{passwordErrors.currentPassword}</div>
				{/if}
			</div>

			<div class="form-group">
				<label for="new-password">New Password</label>
				<input
					type="password"
					id="new-password"
					class="form-input"
					bind:value={newPassword}
					onblur={() => validatePasswordField('newPassword')}
					disabled={passwordSubmitting}
					required
					minlength="8"
				/>
				{#if passwordTouched.newPassword && passwordErrors.newPassword}
					<div class="field-error">{passwordErrors.newPassword}</div>
				{:else}
					<small class="text-muted">Must be at least 8 characters</small>
				{/if}
			</div>

			<div class="form-group">
				<label for="confirm-password">Confirm New Password</label>
				<input
					type="password"
					id="confirm-password"
					class="form-input"
					bind:value={confirmPassword}
					onblur={() => validatePasswordField('confirmPassword')}
					disabled={passwordSubmitting}
					required
				/>
				{#if passwordTouched.confirmPassword && passwordErrors.confirmPassword}
					<div class="field-error">{passwordErrors.confirmPassword}</div>
				{/if}
			</div>

			<button type="submit" class="btn btn-primary" disabled={passwordSubmitting}>
				{passwordSubmitting ? 'Updating...' : 'Change Password'}
			</button>
		</form>
	</div>
</main>

<style>
	h1 {
		font-size: 1.75rem;
		font-weight: 600;
		color: var(--text-primary);
	}

	h2 {
		font-size: 1.25rem;
		font-weight: 600;
		color: var(--text-primary);
		margin-bottom: 0.5rem;
	}

	.text-muted {
		color: var(--text-muted);
		font-size: 0.875rem;
	}

	.field-error {
		color: var(--error-color, #e53e3e);
		font-size: 0.875rem;
		margin-top: 0.25rem;
	}

	small {
		display: block;
		margin-top: 0.25rem;
	}
</style>
