<script lang="ts">
	import { createEventDispatcher } from 'svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { FeedSource, FeedType } from '$lib/types';

	export let editingSource: FeedSource | null = null;

	const dispatch = createEventDispatcher();

	let formData = {
		name: '',
		url: '',
		description: '',
		type: 'article' as FeedType,
		is_active: true,
		is_featured: false,
		fetch_interval_hours: 6
	};

	$: isEditing = editingSource !== null;
	$: submitButtonText = isEditing ? 'Update Source' : 'Create Source';

	$: if (editingSource) {
		formData = {
			name: editingSource.name,
			url: editingSource.url,
			description: editingSource.description || '',
			type: editingSource.type,
			is_active: editingSource.is_active,
			is_featured: editingSource.is_featured,
			fetch_interval_hours: editingSource.fetch_interval_hours
		};
	}

	export function reset() {
		formData = {
			name: '',
			url: '',
			description: '',
			type: 'article',
			is_active: true,
			is_featured: false,
			fetch_interval_hours: 6
		};
		editingSource = null;
	}

	async function handleSubmit() {
		try {
			const data = {
				name: formData.name,
				url: formData.url,
				description: formData.description.trim() || null,
				type: formData.type,
				is_active: formData.is_active,
				is_featured: formData.is_featured,
				fetch_interval_hours: formData.fetch_interval_hours
			};

			if (isEditing && editingSource) {
				await api.put(`/api/news/sources/${editingSource.id}`, data);
				toasts.show('Feed source updated successfully', 'success');
			} else {
				await api.post('/api/news/sources', data);
				toasts.show('Feed source created successfully', 'success');
			}

			reset();
			dispatch('success');
		} catch (error) {
			toasts.show(
				`Error ${isEditing ? 'updating' : 'creating'} feed source: ` + (error as Error).message,
				'error'
			);
		}
	}

	async function handleDelete() {
		if (!editingSource) return;

		const confirmDelete = confirm(
			'Are you sure you want to delete this feed source? This will also delete all articles from this source. This action cannot be undone.'
		);

		if (!confirmDelete) return;

		try {
			await api.delete(`/api/news/sources/${editingSource.id}`);
			toasts.show('Feed source deleted successfully', 'success');
			reset();
			dispatch('success');
		} catch (error) {
			toasts.show('Error deleting feed source: ' + (error as Error).message, 'error');
		}
	}
</script>

<div class="feed-source-form-container">
	<form class="card" on:submit|preventDefault={handleSubmit}>
		<div class="form-group">
			<label for="name" class="block text-sm font-medium text-gray-700">Name</label>
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
			<label for="url" class="block text-sm font-medium text-gray-700">Feed URL</label>
			<input
				type="url"
				id="url"
				name="url"
				required
				class="form-input mt-1"
				placeholder="https://example.com/feed.xml"
				bind:value={formData.url}
			/>
		</div>

		<div class="form-group">
			<label for="description" class="block text-sm font-medium text-gray-700">Description</label>
			<textarea
				id="description"
				name="description"
				rows="2"
				class="form-textarea mt-1"
				bind:value={formData.description}
			></textarea>
		</div>

		<div class="form-group">
			<label for="type" class="block text-sm font-medium text-gray-700">Type</label>
			<select id="type" name="type" class="form-select mt-1" bind:value={formData.type}>
				<option value="article">Article</option>
				<option value="paper">Paper</option>
			</select>
		</div>

		<div class="form-group">
			<label for="fetch_interval_hours" class="block text-sm font-medium text-gray-700"
				>Fetch Interval (hours)</label
			>
			<input
				type="number"
				id="fetch_interval_hours"
				name="fetch_interval_hours"
				min="1"
				max="168"
				class="form-input mt-1"
				bind:value={formData.fetch_interval_hours}
			/>
		</div>

		<div class="form-group flex items-center gap-6">
			<label class="flex items-center gap-2 cursor-pointer">
				<input type="checkbox" class="form-checkbox" bind:checked={formData.is_active} />
				<span class="text-sm font-medium text-gray-700">Active</span>
			</label>

			<label class="flex items-center gap-2 cursor-pointer">
				<input type="checkbox" class="form-checkbox" bind:checked={formData.is_featured} />
				<span class="text-sm font-medium text-gray-700">Featured</span>
			</label>
		</div>

		<div class="form-submit">
			<div class="form-actions">
				<button type="submit" class="btn btn-primary flex-1">{submitButtonText}</button>
				{#if isEditing}
					<button
						type="button"
						class="btn btn-danger btn-delete"
						on:click={handleDelete}
						title="Delete feed source"
					>
						Delete
					</button>
				{/if}
			</div>
		</div>
	</form>
</div>
