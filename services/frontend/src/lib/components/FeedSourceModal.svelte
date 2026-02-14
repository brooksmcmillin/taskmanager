<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Modal from './Modal.svelte';
	import FeedSourceForm from './FeedSourceForm.svelte';
	import type { FeedSource } from '$lib/types';

	const dispatch = createEventDispatcher();

	let modal: Modal;
	let feedSourceForm: FeedSourceForm;
	let editingSource: FeedSource | null = null;
	let modalTitle = 'Add Feed Source';

	export function open() {
		editingSource = null;
		modalTitle = 'Add Feed Source';
		if (feedSourceForm) feedSourceForm.reset();
		modal.openModal();
	}

	export function openEdit(source: FeedSource) {
		editingSource = source;
		modalTitle = 'Edit Feed Source';
		modal.openModal();
	}

	function handleSuccess() {
		modal.closeModal();
		if (feedSourceForm) feedSourceForm.reset();
		dispatch('success');
	}

	function handleClose() {
		if (feedSourceForm) feedSourceForm.reset();
		editingSource = null;
		modalTitle = 'Add Feed Source';
	}
</script>

<Modal bind:this={modal} title={modalTitle} on:close={handleClose}>
	<FeedSourceForm bind:this={feedSourceForm} bind:editingSource on:success={handleSuccess} />
</Modal>
