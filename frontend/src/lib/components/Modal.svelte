<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { browser } from '$app/environment';

	export let title: string;
	export let show = false;

	const dispatch = createEventDispatcher();

	function closeModal() {
		show = false;
		dispatch('close');
		if (browser) {
			document.body.style.overflow = '';
		}
	}

	export function openModal() {
		show = true;
		if (browser) {
			document.body.style.overflow = 'hidden';
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape' && show) {
			closeModal();
		}
	}

	function handleBackdropClick(event: MouseEvent) {
		if (event.target === event.currentTarget) {
			closeModal();
		}
	}

	$: if (browser && show) {
		document.body.style.overflow = 'hidden';
	} else if (browser) {
		document.body.style.overflow = '';
	}
</script>

<svelte:window on:keydown={handleKeydown} />

{#if show}
	<div class="modal show" on:click={handleBackdropClick} role="dialog" aria-modal="true">
		<div class="modal-content">
			<div class="modal-header">
				<h2>{title}</h2>
				<button class="close" on:click={closeModal} aria-label="Close modal">&times;</button>
			</div>
			<div class="modal-body">
				<slot />
			</div>
		</div>
	</div>
{/if}
