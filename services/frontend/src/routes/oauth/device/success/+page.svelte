<svelte:head>
	<title>Device Authorized</title>
</svelte:head>

<div class="page-container">
	<div class="result-container">
		<div class="card">
			<div class="status-icon">✅</div>
			<h1>Device Authorized Successfully</h1>
			<p class="result-message">
				Your device has been authorized. You can now close this window and return to your device.
			</p>
			<div class="actions">
				<a href="/" class="btn btn-primary">Return to Dashboard</a>
			</div>
		</div>
	</div>
</div>

<style>
	.page-container {
		min-height: 100vh;
		background-color: var(--bg-page, #faf8f6);
		padding: 2rem 1rem;
	}

	.result-container {
		display: flex;
		justify-content: center;
		align-items: center;
		min-height: calc(100vh - 4rem);
	}

	.card {
		max-width: 480px;
		width: 100%;
		padding: 3rem 2rem;
		background: var(--bg-card, #ffffff);
		border-radius: var(--radius-xl, 1.25rem);
		box-shadow: var(--shadow-lg, 0 10px 15px -3px rgb(28 25 23 / 0.07));
		border: 1px solid var(--border-light, #f3f0ec);
		text-align: center;
	}

	.status-icon {
		font-size: 3.5rem;
		margin-bottom: 1.25rem;
	}

	.card h1 {
		margin-bottom: 1rem;
		font-size: 1.5rem;
		font-weight: 700;
		color: var(--success-600, #15803d);
	}

	.result-message {
		margin-bottom: 2rem;
		color: var(--text-secondary, #57534e);
		font-size: 0.9375rem;
		line-height: 1.6;
	}

	.actions {
		margin-top: 2rem;
	}

	.btn-primary {
		display: inline-block;
		padding: 0.625rem 1.5rem;
		border-radius: var(--radius-md, 0.625rem);
		font-size: 0.9375rem;
		font-weight: 600;
		border: none;
		cursor: pointer;
		transition: all 0.2s ease;
		font-family: inherit;
		background-color: var(--primary-600, #c05621);
		color: white;
		text-decoration: none;
	}

	.btn-primary:hover {
		background-color: var(--primary-700, #9a4419);
		transform: translateY(-1px);
		box-shadow: var(--shadow-md);
	}
</style>
