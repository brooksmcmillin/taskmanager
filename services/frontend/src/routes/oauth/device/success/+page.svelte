<svelte:head>
	<title>Device Authorized</title>
</svelte:head>

<div class="container">
	<div class="success-container">
		<div class="card">
			<div class="success-icon">✅</div>
			<h1>Device Authorized Successfully</h1>
			<p class="success-message">
				Your device has been authorized. You can now close this window and return to your device.
			</p>
			<div class="actions">
				<a href="/" class="btn btn-primary">Return to Dashboard</a>
			</div>
		</div>
	</div>
</div>

<style>
	.success-container {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: 60vh;
		padding: 2rem;
	}

	.card {
		max-width: 480px;
		width: 100%;
		padding: 3rem 2rem;
		background: var(--card-bg, white);
		border-radius: 1rem;
		box-shadow:
			0 4px 6px -1px rgba(0, 0, 0, 0.1),
			0 2px 4px -1px rgba(0, 0, 0, 0.06);
		text-align: center;
	}

	.success-icon {
		font-size: 4rem;
		margin-bottom: 1.5rem;
	}

	.card h1 {
		margin-bottom: 1rem;
		color: var(--success-color, #10b981);
	}

	.success-message {
		margin-bottom: 2rem;
		color: var(--text-secondary, #64748b);
		line-height: 1.6;
	}

	.actions {
		margin-top: 2rem;
	}
</style>
