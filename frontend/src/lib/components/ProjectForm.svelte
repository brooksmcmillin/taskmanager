<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { projects } from '$lib/stores/projects';
	import type { Project } from '$lib/types';

	export let editingProject: Project | null = null;

	const dispatch = createEventDispatcher();

	let formData = {
		name: '',
		description: '',
		color: '#3b82f6'
	};

	$: isEditing = editingProject !== null;
	$: submitButtonText = isEditing ? 'Update Project' : 'Create Project';

	$: if (editingProject) {
		formData = {
			name: editingProject.name,
			description: editingProject.description || '',
			color: editingProject.color || '#3b82f6'
		};
	}

	export function reset() {
		formData = {
			name: '',
			description: '',
			color: '#3b82f6'
		};
		editingProject = null;
	}

	async function handleSubmit() {
		try {
			const projectData = {
				name: formData.name,
				description: formData.description || undefined,
				color: formData.color
			};

			if (isEditing && editingProject) {
				await projects.updateProject(editingProject.id, projectData);
			} else {
				await projects.add(projectData);
			}

			reset();
			dispatch('success');
		} catch (error) {
			alert(
				`Error ${isEditing ? 'updating' : 'creating'} project: ` + (error as Error).message
			);
		}
	}

	async function handleDelete() {
		if (!editingProject) return;

		const confirmDelete = confirm(
			'Are you sure you want to delete this project? This will also delete all todos associated with this project. This action cannot be undone.'
		);

		if (!confirmDelete) return;

		try {
			await projects.remove(editingProject.id);
			reset();
			dispatch('success');
		} catch (error) {
			alert('Error deleting project: ' + (error as Error).message);
		}
	}
</script>

<div class="project-form-container">
	<form class="card" on:submit|preventDefault={handleSubmit}>
		<div class="form-group">
			<label for="name" class="block text-sm font-medium text-gray-700">Project Name</label>
			<input
				type="text"
				id="name"
				name="name"
				required
				class="form-input mt-1"
				bind:value={formData.name}
			/>
		</div>

		<div class="form-group">
			<label for="description" class="block text-sm font-medium text-gray-700"
				>Description</label
			>
			<textarea
				id="description"
				name="description"
				rows="3"
				class="form-textarea mt-1"
				bind:value={formData.description}
			></textarea>
		</div>

		<div class="form-group">
			<label for="color" class="block text-sm font-medium text-gray-700">Color</label>
			<input
				type="color"
				id="color"
				name="color"
				class="form-input mt-1 h-10"
				bind:value={formData.color}
			/>
		</div>

		<div class="form-submit">
			<div class="form-actions">
				<button type="submit" class="btn btn-primary flex-1">{submitButtonText}</button>
				{#if isEditing}
					<button
						type="button"
						class="btn btn-danger btn-delete"
						on:click={handleDelete}
						title="Delete project"
					>
						🗑️
					</button>
				{/if}
			</div>
		</div>
	</form>
</div>
