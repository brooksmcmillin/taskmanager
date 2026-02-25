<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import { toasts } from '$lib/stores/ui';
	import type { Toast } from '$lib/stores/ui';

	function handleAction(toast: Toast) {
		if (toast.action) {
			toast.action.callback();
			toasts.dismiss(toast.id);
		}
	}

	function typeIcon(type: Toast['type']): string {
		switch (type) {
			case 'success':
				return '\u2713';
			case 'error':
				return '!';
			case 'warning':
				return '\u26A0';
			case 'info':
			default:
				return 'i';
		}
	}
</script>

<div class="toasts-container" aria-live="polite">
	{#each $toasts as toast (toast.id)}
		<div
			class="toast toast-{toast.type}"
			role="alert"
			in:fly={{ y: 40, duration: 250 }}
			out:fade={{ duration: 150 }}
		>
			<span class="toast-icon toast-icon-{toast.type}">{typeIcon(toast.type)}</span>
			<span class="toast-message">{toast.message}</span>
			{#if toast.action}
				<button class="toast-action" on:click={() => handleAction(toast)}>
					{toast.action.label}
				</button>
			{/if}
			<button class="toast-dismiss" on:click={() => toasts.dismiss(toast.id)} aria-label="Dismiss"
				>&times;</button
			>
		</div>
	{/each}
</div>

<style>
	.toasts-container {
		position: fixed;
		bottom: 1.5rem;
		right: 1.5rem;
		z-index: 9999;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		max-width: 24rem;
		pointer-events: none;
	}

	.toast {
		display: flex;
		align-items: center;
		gap: 0.625rem;
		padding: 0.75rem 1rem;
		border-radius: var(--radius-lg, 0.5rem);
		background: var(--bg-card, #fff);
		border: 1px solid var(--border-color, #e5e7eb);
		box-shadow:
			0 4px 12px rgba(0, 0, 0, 0.1),
			0 1px 3px rgba(0, 0, 0, 0.06);
		font-size: 0.875rem;
		color: var(--text-primary, #1f2937);
		pointer-events: auto;
	}

	.toast-icon {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.25rem;
		height: 1.25rem;
		border-radius: 50%;
		font-size: 0.6875rem;
		font-weight: 700;
		flex-shrink: 0;
		line-height: 1;
	}

	.toast-icon-success {
		background: var(--success-100, #dcfce7);
		color: var(--success-600, #16a34a);
	}

	.toast-icon-error {
		background: var(--error-100, #fee2e2);
		color: var(--error-600, #dc2626);
	}

	.toast-icon-warning {
		background: var(--warning-100, #fef3c7);
		color: var(--warning-600, #d97706);
	}

	.toast-icon-info {
		background: var(--primary-100, #dbeafe);
		color: var(--primary-600, #2563eb);
	}

	.toast-message {
		flex: 1;
		line-height: 1.4;
	}

	.toast-action {
		padding: 0.25rem 0.625rem;
		border: none;
		border-radius: var(--radius, 0.375rem);
		background: var(--primary-600, #2563eb);
		color: #fff;
		font-size: 0.75rem;
		font-weight: 600;
		cursor: pointer;
		white-space: nowrap;
		transition: background 0.15s ease;
		flex-shrink: 0;
	}

	.toast-action:hover {
		background: var(--primary-700, #1d4ed8);
	}

	.toast-dismiss {
		padding: 0;
		border: none;
		background: none;
		font-size: 1.125rem;
		line-height: 1;
		color: var(--text-muted, #9ca3af);
		cursor: pointer;
		flex-shrink: 0;
		transition: color 0.15s ease;
	}

	.toast-dismiss:hover {
		color: var(--text-primary, #1f2937);
	}

	@media (max-width: 768px) {
		.toasts-container {
			left: 1rem;
			right: 1rem;
			bottom: 1rem;
			max-width: none;
		}
	}
</style>
