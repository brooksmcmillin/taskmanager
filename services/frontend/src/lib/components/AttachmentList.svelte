<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { todos } from '$lib/stores/todos';
	import type { Attachment } from '$lib/types';

	export let todoId: number;
	export let attachments: Attachment[] = [];

	let fileInput: HTMLInputElement;
	let isUploading = false;
	let uploadError = '';

	const dispatch = createEventDispatcher();

	onMount(async () => {
		if (attachments.length === 0) {
			try {
				attachments = await todos.loadAttachments(todoId);
			} catch (error) {
				console.error('Failed to load attachments:', error);
			}
		}
	});

	function triggerFileSelect() {
		fileInput?.click();
	}

	async function handleFileSelect(event: Event) {
		const input = event.target as HTMLInputElement;
		const file = input.files?.[0];
		if (!file) return;

		uploadError = '';
		isUploading = true;

		try {
			await todos.uploadAttachment(todoId, file);
			attachments = await todos.loadAttachments(todoId);
			dispatch('attachmentAdded');
		} catch (error) {
			uploadError = error instanceof Error ? error.message : 'Upload failed';
			console.error('Failed to upload attachment:', error);
		} finally {
			isUploading = false;
			input.value = '';
		}
	}

	async function handleDelete(attachmentId: number) {
		if (!confirm('Delete this attachment?')) return;

		try {
			await todos.removeAttachment(todoId, attachmentId);
			attachments = attachments.filter((a) => a.id !== attachmentId);
			dispatch('attachmentDeleted', attachmentId);
		} catch (error) {
			console.error('Failed to delete attachment:', error);
		}
	}

	function openAttachment(attachment: Attachment) {
		const url = todos.getAttachmentUrl(todoId, attachment.id);
		window.open(url, '_blank');
	}

	function formatFileSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}
</script>

<div class="attachment-list">
	<div class="attachment-header">
		<h4 class="attachment-title">
			Attachments
			{#if attachments.length > 0}
				<span class="attachment-count">({attachments.length})</span>
			{/if}
		</h4>
		<button
			class="add-attachment-btn"
			on:click={triggerFileSelect}
			disabled={isUploading}
			title="Add attachment"
		>
			{#if isUploading}
				<span class="spinner"></span>
			{:else}
				+
			{/if}
		</button>
		<input
			bind:this={fileInput}
			type="file"
			accept="image/jpeg,image/png,image/gif,image/webp"
			on:change={handleFileSelect}
			class="hidden-input"
		/>
	</div>

	{#if uploadError}
		<div class="error-message">{uploadError}</div>
	{/if}

	{#if attachments.length > 0}
		<div class="attachment-grid">
			{#each attachments as attachment (attachment.id)}
				<div class="attachment-item">
					<button class="attachment-preview" on:click={() => openAttachment(attachment)}>
						<img
							src={todos.getAttachmentUrl(todoId, attachment.id)}
							alt={attachment.filename}
							loading="lazy"
						/>
					</button>
					<div class="attachment-info">
						<span class="attachment-name" title={attachment.filename}>
							{attachment.filename}
						</span>
						<span class="attachment-size">{formatFileSize(attachment.file_size)}</span>
					</div>
					<button
						class="delete-btn"
						on:click={() => handleDelete(attachment.id)}
						title="Delete attachment"
					>
						<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
							<path d="M6 18L18 6M6 6l12 12" />
						</svg>
					</button>
				</div>
			{/each}
		</div>
	{:else if !isUploading}
		<p class="no-attachments">No attachments yet. Click + to add one.</p>
	{/if}
</div>

<style>
	.attachment-list {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid #e5e7eb;
	}

	.attachment-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.attachment-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: #374151;
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.attachment-count {
		font-weight: 400;
		color: #6b7280;
		margin-left: 0.5rem;
	}

	.add-attachment-btn {
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px dashed #9ca3af;
		background: transparent;
		color: #6b7280;
		font-size: 1.25rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all 0.2s;
	}

	.add-attachment-btn:hover:not(:disabled) {
		border-color: #3b82f6;
		color: #3b82f6;
		background-color: #eff6ff;
	}

	.add-attachment-btn:disabled {
		cursor: wait;
	}

	.hidden-input {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		border: 0;
	}

	.spinner {
		width: 1rem;
		height: 1rem;
		border: 2px solid #e5e7eb;
		border-top-color: #3b82f6;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.error-message {
		background-color: #fef2f2;
		border: 1px solid #fecaca;
		color: #dc2626;
		padding: 0.5rem 0.75rem;
		border-radius: 0.375rem;
		font-size: 0.875rem;
		margin-bottom: 0.75rem;
	}

	.attachment-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
		gap: 0.75rem;
	}

	.attachment-item {
		position: relative;
		background-color: #f9fafb;
		border-radius: 0.5rem;
		overflow: hidden;
		border: 1px solid #e5e7eb;
	}

	.attachment-preview {
		width: 100%;
		aspect-ratio: 1;
		padding: 0;
		border: none;
		background: #f3f4f6;
		cursor: pointer;
		display: block;
	}

	.attachment-preview img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.attachment-preview:hover img {
		opacity: 0.9;
	}

	.attachment-info {
		padding: 0.5rem;
	}

	.attachment-name {
		display: block;
		font-size: 0.75rem;
		color: #374151;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.attachment-size {
		font-size: 0.625rem;
		color: #9ca3af;
	}

	.delete-btn {
		position: absolute;
		top: 0.25rem;
		right: 0.25rem;
		width: 1.5rem;
		height: 1.5rem;
		border: none;
		background: rgba(255, 255, 255, 0.9);
		color: #6b7280;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.25rem;
		opacity: 0;
		transition: all 0.2s;
	}

	.attachment-item:hover .delete-btn {
		opacity: 1;
	}

	.delete-btn:hover {
		color: #ef4444;
		background: white;
	}

	.delete-btn svg {
		width: 1rem;
		height: 1rem;
	}

	.no-attachments {
		font-size: 0.875rem;
		color: #9ca3af;
		text-align: center;
		padding: 1rem 0;
		margin: 0;
	}
</style>
