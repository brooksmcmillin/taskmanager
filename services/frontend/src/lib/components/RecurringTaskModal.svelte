<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import Modal from './Modal.svelte';
	import RecurringTaskForm from './RecurringTaskForm.svelte';
	import type { RecurringTask } from '$lib/types';

	const dispatch = createEventDispatcher();

	let modal: Modal;
	let taskForm: RecurringTaskForm;
	let editingTask: RecurringTask | null = null;
	let modalTitle = 'Create Recurring Task';

	export function open() {
		editingTask = null;
		modalTitle = 'Create Recurring Task';
		if (taskForm) taskForm.reset();
		modal.openModal();
	}

	export function openEdit(task: RecurringTask) {
		editingTask = task;
		modalTitle = 'Edit Recurring Task';
		modal.openModal();
	}

	function handleSuccess() {
		modal.closeModal();
		if (taskForm) taskForm.reset();
		dispatch('save');
	}

	function handleClose() {
		if (taskForm) taskForm.reset();
		editingTask = null;
		modalTitle = 'Create Recurring Task';
	}
</script>

<Modal bind:this={modal} title={modalTitle} on:close={handleClose}>
	<RecurringTaskForm bind:this={taskForm} bind:editingTask on:success={handleSuccess} />
</Modal>

<button class="add-recurring-btn" on:click={open}>
	<span class="plus-icon">+</span>
</button>

<style>
	.add-recurring-btn {
		position: fixed;
		bottom: 2rem;
		right: 2rem;
		width: 3.5rem;
		height: 3.5rem;
		border-radius: 50%;
		background-color: #2563eb;
		color: white;
		border: none;
		box-shadow: 0 4px 12px rgba(37, 99, 235, 0.4);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s ease-in-out;
		z-index: 40;
	}

	.add-recurring-btn:hover {
		background-color: #1d4ed8;
		transform: scale(1.05);
	}

	.plus-icon {
		font-size: 1.75rem;
		font-weight: 300;
		line-height: 1;
	}
</style>
