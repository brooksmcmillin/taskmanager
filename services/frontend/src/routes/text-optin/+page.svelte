<script lang="ts">
	let phone = '';
	let name = '';
	let consent = false;
	let submitted = false;
	let error = '';
	let submitting = false;

	function formatPhone(value: string): string {
		const digits = value.replace(/\D/g, '');
		if (digits.length <= 3) return digits;
		if (digits.length <= 6) return `(${digits.slice(0, 3)}) ${digits.slice(3)}`;
		return `(${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 10)}`;
	}

	function handlePhoneInput(e: Event) {
		const input = e.target as HTMLInputElement;
		const digits = input.value.replace(/\D/g, '');
		phone = formatPhone(digits);
	}

	function validatePhone(value: string): boolean {
		const digits = value.replace(/\D/g, '');
		return digits.length === 10;
	}

	async function handleSubmit() {
		error = '';

		if (!validatePhone(phone)) {
			error = 'Please enter a valid 10-digit phone number.';
			return;
		}

		if (!consent) {
			error = 'You must agree to receive text messages.';
			return;
		}

		submitting = true;

		// Simulate a short delay since there's no real backend endpoint yet
		await new Promise((resolve) => setTimeout(resolve, 500));

		// Log the opt-in for now — wire up to a real endpoint later
		const digits = phone.replace(/\D/g, '');
		console.log('Text opt-in:', { phone: `+1${digits}`, name: name.trim() || null });

		submitting = false;
		submitted = true;
	}
</script>

<svelte:head>
	<title>Text Message Opt-In</title>
</svelte:head>

<main class="container" style="max-width: 480px; margin: 3rem auto;">
	<div class="card">
		{#if submitted}
			<div class="success-state">
				<div class="success-icon">&#10003;</div>
				<h1>You're signed up!</h1>
				<p class="success-phone">+1 {phone}</p>
				<p class="success-message">
					You'll receive text message updates at this number.
				</p>
				<button
					class="btn btn-outline"
					style="width: 100%; margin-left: 0;"
					on:click={() => {
						submitted = false;
						phone = '';
						name = '';
						consent = false;
					}}
				>
					Sign up another number
				</button>
			</div>
		{:else}
			<h1>Get Text Updates</h1>
			<p class="subtitle">
				Enter your phone number to receive text message notifications.
			</p>

			<form on:submit|preventDefault={handleSubmit} novalidate>
				<div class="form-group">
					<label for="name">Name <span class="optional">(optional)</span></label>
					<input
						type="text"
						id="name"
						class="form-input"
						bind:value={name}
						placeholder="Your name"
					/>
				</div>

				<div class="form-group">
					<label for="phone">Phone Number</label>
					<div class="phone-input-wrapper">
						<span class="country-code">+1</span>
						<input
							type="tel"
							id="phone"
							class="form-input phone-input"
							value={phone}
							on:input={handlePhoneInput}
							placeholder="(555) 123-4567"
							maxlength="14"
							required
						/>
					</div>
				</div>

				<div class="consent-group">
					<label class="consent-label">
						<input type="checkbox" bind:checked={consent} />
						<span>
							I agree to receive text messages. Message &amp; data rates may apply.
							Reply STOP to unsubscribe.
						</span>
					</label>
				</div>

				{#if error}
					<div class="error-message">{error}</div>
				{/if}

				<button
					type="submit"
					class="btn btn-primary"
					style="width: 100%; margin-left: 0;"
					disabled={submitting}
				>
					{submitting ? 'Signing up...' : 'Sign Up for Texts'}
				</button>
			</form>

			<p class="fine-print">
				By opting in, you consent to receive automated text messages at the number provided.
				Consent is not a condition of purchase. Message frequency varies.
				Reply HELP for help, STOP to cancel.
				See our <a href="/privacy">Privacy Policy</a> and <a href="/terms">Terms and Conditions</a>.
			</p>
		{/if}
	</div>
</main>

<style>
	h1 {
		margin-bottom: 0.25rem;
		font-size: 1.5rem;
	}

	.subtitle {
		color: var(--text-muted);
		margin-bottom: 1.5rem;
		font-size: 0.9375rem;
	}

	.optional {
		color: var(--text-muted);
		font-weight: 400;
		font-size: 0.8125rem;
	}

	.phone-input-wrapper {
		display: flex;
		align-items: center;
		gap: 0;
	}

	.country-code {
		display: flex;
		align-items: center;
		padding: 0 0.75rem;
		height: 38px;
		background: var(--bg-secondary, #f5f5f5);
		border: 1px solid var(--border-color, #d1d5db);
		border-right: none;
		border-radius: var(--radius, 6px) 0 0 var(--radius, 6px);
		color: var(--text-muted);
		font-size: 0.875rem;
		font-weight: 500;
	}

	.phone-input {
		border-top-left-radius: 0 !important;
		border-bottom-left-radius: 0 !important;
	}

	.consent-group {
		margin: 1.25rem 0;
	}

	.consent-label {
		display: flex;
		align-items: flex-start;
		gap: 0.625rem;
		cursor: pointer;
		font-size: 0.875rem;
		line-height: 1.4;
		color: var(--text-secondary);
	}

	.consent-label input[type='checkbox'] {
		margin-top: 2px;
		flex-shrink: 0;
		width: 16px;
		height: 16px;
		cursor: pointer;
	}

	.fine-print {
		margin-top: 1.25rem;
		font-size: 0.75rem;
		color: var(--text-muted);
		line-height: 1.5;
	}

	/* Success state */
	.success-state {
		text-align: center;
		padding: 1rem 0;
	}

	.success-icon {
		width: 56px;
		height: 56px;
		border-radius: 50%;
		background: var(--success-color, #059669);
		color: white;
		display: flex;
		align-items: center;
		justify-content: center;
		font-size: 1.75rem;
		margin: 0 auto 1rem;
	}

	.success-state h1 {
		margin-bottom: 0.5rem;
	}

	.success-phone {
		font-size: 1.125rem;
		font-weight: 600;
		color: var(--text-primary);
		margin-bottom: 0.5rem;
	}

	.success-message {
		color: var(--text-muted);
		margin-bottom: 1.5rem;
		font-size: 0.9375rem;
	}
</style>
