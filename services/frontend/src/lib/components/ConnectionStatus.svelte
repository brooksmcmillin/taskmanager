<script lang="ts">
	import { connectionState, type ConnectionState } from '$lib/services/eventStream';

	let state: ConnectionState = $state('disconnected');
	const unsub = connectionState.subscribe((s) => (state = s));

	import { onDestroy } from 'svelte';
	onDestroy(unsub);
</script>

{#if state !== 'connected'}
	<span
		class="connection-dot"
		class:connecting={state === 'connecting'}
		class:disconnected={state === 'disconnected'}
		title={state === 'connecting' ? 'Reconnecting...' : 'Disconnected'}
		aria-label={state === 'connecting' ? 'Reconnecting to server' : 'Disconnected from server'}
	></span>
{/if}

<style>
	.connection-dot {
		display: inline-block;
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 9999px;
		flex-shrink: 0;
	}

	.connecting {
		background-color: var(--warning-500, #f59e0b);
		animation: pulse 1.5s ease-in-out infinite;
	}

	.disconnected {
		background-color: var(--error-500, #ef4444);
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 1;
		}
		50% {
			opacity: 0.4;
		}
	}
</style>
