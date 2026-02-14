<script lang="ts">
	import { createEventDispatcher, onMount } from 'svelte';
	import { todos } from '$lib/stores/todos';
	import type { Comment } from '$lib/types';

	export let todoId: number;
	export let comments: Comment[] = [];

	let showAddForm = false;
	let newCommentContent = '';
	let isSubmitting = false;
	let editingId: number | null = null;
	let editContent = '';

	const dispatch = createEventDispatcher();

	onMount(async () => {
		if (comments.length === 0) {
			try {
				comments = await todos.loadComments(todoId);
			} catch (error) {
				console.error('Failed to load comments:', error);
			}
		}
	});

	async function handleAddComment() {
		if (!newCommentContent.trim() || isSubmitting) return;

		isSubmitting = true;
		try {
			await todos.addComment(todoId, { content: newCommentContent.trim() });
			comments = await todos.loadComments(todoId);
			newCommentContent = '';
			showAddForm = false;
			dispatch('commentAdded');
		} catch (error) {
			console.error('Failed to add comment:', error);
		} finally {
			isSubmitting = false;
		}
	}

	function startEdit(comment: Comment) {
		editingId = comment.id;
		editContent = comment.content;
	}

	function cancelEdit() {
		editingId = null;
		editContent = '';
	}

	async function handleSaveEdit() {
		if (!editContent.trim() || !editingId || isSubmitting) return;

		isSubmitting = true;
		try {
			await todos.updateComment(todoId, editingId, editContent.trim());
			comments = await todos.loadComments(todoId);
			editingId = null;
			editContent = '';
			dispatch('commentUpdated');
		} catch (error) {
			console.error('Failed to update comment:', error);
		} finally {
			isSubmitting = false;
		}
	}

	async function handleDeleteComment(commentId: number) {
		if (!confirm('Delete this comment?')) return;
		try {
			await todos.removeComment(todoId, commentId);
			comments = comments.filter((c) => c.id !== commentId);
			dispatch('commentDeleted', commentId);
		} catch (error) {
			console.error('Failed to delete comment:', error);
		}
	}

	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			showAddForm = false;
			newCommentContent = '';
		}
	}

	function handleEditKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			cancelEdit();
		}
	}

	function formatTimestamp(dateStr: string): string {
		const date = new Date(dateStr);
		return date.toLocaleString();
	}
</script>

<div class="comment-list">
	<div class="comment-header">
		<h4 class="comment-title">
			Comments
			{#if comments.length > 0}
				<span class="comment-count">({comments.length})</span>
			{/if}
		</h4>
		{#if !showAddForm}
			<button class="add-comment-btn" on:click={() => (showAddForm = true)} title="Add comment">
				+
			</button>
		{/if}
	</div>

	{#if showAddForm}
		<div class="add-comment-form">
			<textarea
				bind:value={newCommentContent}
				placeholder="Write a comment..."
				class="comment-textarea"
				on:keydown={handleKeydown}
				rows="3"
			></textarea>
			<div class="form-actions">
				<button
					class="btn btn-sm btn-primary"
					on:click={handleAddComment}
					disabled={isSubmitting || !newCommentContent.trim()}
				>
					{isSubmitting ? 'Adding...' : 'Add'}
				</button>
				<button
					class="btn btn-sm btn-secondary"
					on:click={() => {
						showAddForm = false;
						newCommentContent = '';
					}}
				>
					Cancel
				</button>
			</div>
		</div>
	{/if}

	{#if comments.length > 0}
		<ul class="comment-items">
			{#each comments as comment (comment.id)}
				<li class="comment-item">
					{#if editingId === comment.id}
						<div class="edit-comment-form">
							<textarea
								bind:value={editContent}
								class="comment-textarea"
								on:keydown={handleEditKeydown}
								rows="3"
							></textarea>
							<div class="form-actions">
								<button
									class="btn btn-sm btn-primary"
									on:click={handleSaveEdit}
									disabled={isSubmitting || !editContent.trim()}
								>
									{isSubmitting ? 'Saving...' : 'Save'}
								</button>
								<button class="btn btn-sm btn-secondary" on:click={cancelEdit}> Cancel </button>
							</div>
						</div>
					{:else}
						<div class="comment-content">
							<p class="comment-text">{comment.content}</p>
							<span class="comment-timestamp">
								{formatTimestamp(comment.created_at)}
								{#if comment.updated_at}
									<span class="edited-label">(edited)</span>
								{/if}
							</span>
						</div>
						<div class="comment-actions">
							<button class="action-btn" on:click={() => startEdit(comment)} title="Edit comment">
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" />
									<path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" />
								</svg>
							</button>
							<button
								class="action-btn delete-btn"
								on:click={() => handleDeleteComment(comment.id)}
								title="Delete comment"
							>
								<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
									<path d="M6 18L18 6M6 6l12 12" />
								</svg>
							</button>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{:else if !showAddForm}
		<p class="no-comments">No comments yet. Click + to add one.</p>
	{/if}
</div>

<style>
	.comment-list {
		margin-top: 1.5rem;
		padding-top: 1.5rem;
		border-top: 1px solid var(--border-color);
	}

	.comment-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 0.75rem;
	}

	.comment-title {
		font-size: 0.875rem;
		font-weight: 600;
		color: var(--text-secondary);
		margin: 0;
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.comment-count {
		font-weight: 400;
		color: var(--text-muted);
		margin-left: 0.5rem;
	}

	.add-comment-btn {
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 50%;
		border: 1px dashed var(--gray-400);
		background: transparent;
		color: var(--text-muted);
		font-size: 1.25rem;
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		transition: all var(--transition-base);
	}

	.add-comment-btn:hover {
		border-color: var(--primary-500);
		color: var(--primary-500);
		background-color: var(--primary-50);
	}

	.add-comment-form,
	.edit-comment-form {
		background-color: var(--bg-page);
		border-radius: 0.5rem;
		padding: 0.75rem;
		margin-bottom: 1rem;
	}

	.comment-textarea {
		width: 100%;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--gray-300);
		border-radius: 0.375rem;
		font-size: 0.875rem;
		font-family: inherit;
		background-color: var(--bg-input);
		color: var(--text-primary);
		resize: vertical;
		margin-bottom: 0.5rem;
	}

	.comment-textarea:focus {
		outline: none;
		border-color: var(--primary-500);
		box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
	}

	.form-actions {
		display: flex;
		gap: 0.5rem;
		justify-content: flex-end;
	}

	.btn {
		padding: 0.375rem 0.75rem;
		border-radius: 0.375rem;
		font-size: 0.75rem;
		font-weight: 500;
		cursor: pointer;
		border: none;
		transition: all var(--transition-base);
	}

	.btn-sm {
		padding: 0.25rem 0.5rem;
	}

	.btn-primary {
		background-color: var(--primary-500);
		color: white;
	}

	.btn-primary:hover:not(:disabled) {
		background-color: var(--primary-600);
	}

	.btn-primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.btn-secondary {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}

	.btn-secondary:hover {
		background-color: var(--bg-active);
	}

	.comment-items {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.comment-item {
		display: flex;
		gap: 0.75rem;
		padding: 0.75rem 0;
		border-bottom: 1px solid var(--border-light);
	}

	.comment-item:last-child {
		border-bottom: none;
	}

	.comment-content {
		flex: 1;
		min-width: 0;
	}

	.comment-text {
		font-size: 0.875rem;
		color: var(--text-primary);
		line-height: 1.5;
		margin: 0 0 0.25rem 0;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.comment-timestamp {
		font-size: 0.75rem;
		color: var(--text-muted);
	}

	.edited-label {
		font-style: italic;
	}

	.comment-actions {
		display: flex;
		gap: 0.25rem;
		flex-shrink: 0;
		opacity: 0;
		transition: opacity var(--transition-base);
	}

	.comment-item:hover .comment-actions {
		opacity: 1;
	}

	.action-btn {
		width: 1.5rem;
		height: 1.5rem;
		border: none;
		background: transparent;
		color: var(--text-muted);
		cursor: pointer;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 0.25rem;
		transition: all var(--transition-base);
	}

	.action-btn:hover {
		color: var(--primary-500);
		background-color: var(--primary-50);
	}

	.action-btn.delete-btn:hover {
		color: var(--error-500);
		background-color: var(--error-50);
	}

	.action-btn svg {
		width: 1rem;
		height: 1rem;
	}

	.no-comments {
		font-size: 0.875rem;
		color: var(--text-muted);
		text-align: center;
		padding: 1rem 0;
		margin: 0;
	}
</style>
