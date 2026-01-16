<script lang="ts">
	import Modal from './Modal.svelte';
	import TodoForm from './TodoForm.svelte';
	import type { Todo } from '$lib/types';

	let modal: Modal;
	let todoForm: TodoForm;
	let editingTodo: Todo | null = null;
	let modalTitle = 'Add New Todo';

	/**
	 * Opens the modal in "create" mode for adding a new todo
	 */
	export function open() {
		editingTodo = null;
		modalTitle = 'Add New Todo';
		if (todoForm) todoForm.reset();
		modal.openModal();
	}

	/**
	 * Opens the modal in "edit" mode for modifying an existing todo
	 * @param todo - The todo to edit
	 */
	export function openEdit(todo: Todo) {
		editingTodo = todo;
		modalTitle = 'Edit Todo';
		modal.openModal();
	}

	function handleSuccess() {
		modal.closeModal();
		if (todoForm) todoForm.reset();
	}

	function handleClose() {
		if (todoForm) todoForm.reset();
		editingTodo = null;
		modalTitle = 'Add New Todo';
	}
</script>

<Modal bind:this={modal} title={modalTitle} on:close={handleClose}>
	<TodoForm bind:this={todoForm} bind:editingTodo on:success={handleSuccess} />
</Modal>

<button class="add-todo-btn" on:click={open}>
	<span class="plus-icon">+</span>
</button>
