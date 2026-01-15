<script lang="ts">
	import { toasts } from '$lib/stores/ui';
	import type { Toast } from '$lib/stores/ui';

	let toastList: Toast[] = [];

	toasts.subscribe((value) => {
		toastList = value;
	});

	function dismiss(id: number) {
		toasts.dismiss(id);
	}
</script>

<div class="toast-container">
	{#each toastList as toast (toast.id)}
		<div class="toast toast-{toast.type}" role="alert">
			<div class="toast-message">{toast.message}</div>
			<button class="toast-close" on:click={() => dismiss(toast.id)} aria-label="Close">
				&times;
			</button>
		</div>
	{/each}
</div>

<style>
	.toast-container {
		position: fixed;
		top: 1rem;
		right: 1rem;
		z-index: 9999;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 400px;
	}

	.toast {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 1rem 1.25rem;
		border-radius: 0.5rem;
		box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
		animation: slideIn 0.3s ease-out;
		background: white;
		border-left: 4px solid;
	}

	@keyframes slideIn {
		from {
			transform: translateX(100%);
			opacity: 0;
		}
		to {
			transform: translateX(0);
			opacity: 1;
		}
	}

	.toast-success {
		border-left-color: #10b981;
		background-color: #f0fdf4;
	}

	.toast-error {
		border-left-color: #ef4444;
		background-color: #fef2f2;
	}

	.toast-info {
		border-left-color: #3b82f6;
		background-color: #eff6ff;
	}

	.toast-warning {
		border-left-color: #f59e0b;
		background-color: #fffbeb;
	}

	.toast-message {
		flex: 1;
		font-size: 0.875rem;
		line-height: 1.25rem;
		color: #1f2937;
	}

	.toast-close {
		margin-left: 1rem;
		background: none;
		border: none;
		font-size: 1.5rem;
		line-height: 1;
		color: #6b7280;
		cursor: pointer;
		padding: 0;
		width: 1.5rem;
		height: 1.5rem;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.toast-close:hover {
		color: #111827;
	}

	:global([data-theme='dark']) .toast {
		background: #1f2937;
	}

	:global([data-theme='dark']) .toast-message {
		color: #f9fafb;
	}

	:global([data-theme='dark']) .toast-close {
		color: #9ca3af;
	}

	:global([data-theme='dark']) .toast-close:hover {
		color: #f9fafb;
	}

	:global([data-theme='dark']) .toast-success {
		background-color: #064e3b;
	}

	:global([data-theme='dark']) .toast-error {
		background-color: #7f1d1d;
	}

	:global([data-theme='dark']) .toast-info {
		background-color: #1e3a8a;
	}

	:global([data-theme='dark']) .toast-warning {
		background-color: #78350f;
	}
</style>
