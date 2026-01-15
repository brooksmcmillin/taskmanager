<script lang="ts">
	import Modal from './Modal.svelte';
	import ProjectForm from './ProjectForm.svelte';
	import type { Project } from '$lib/types';

	let modal: Modal;
	let projectForm: ProjectForm;
	let editingProject: Project | null = null;
	let modalTitle = 'Add New Project';

	/**
	 * Opens the modal in "create" mode for adding a new project
	 */
	export function open() {
		editingProject = null;
		modalTitle = 'Add New Project';
		if (projectForm) projectForm.reset();
		modal.openModal();
	}

	/**
	 * Opens the modal in "edit" mode for modifying an existing project
	 * @param project - The project to edit
	 */
	export function openEdit(project: Project) {
		editingProject = project;
		modalTitle = 'Edit Project';
		modal.openModal();
	}

	function handleSuccess() {
		modal.closeModal();
		if (projectForm) projectForm.reset();
	}

	function handleClose() {
		if (projectForm) projectForm.reset();
		editingProject = null;
		modalTitle = 'Add New Project';
	}
</script>

<Modal bind:this={modal} title={modalTitle} on:close={handleClose}>
	<ProjectForm bind:this={projectForm} bind:editingProject on:success={handleSuccess} />
</Modal>

<button class="add-project-btn" on:click={open}>
	<span class="plus-icon">+</span>
</button>
