<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import ThemeToggle from './ThemeToggle.svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { User } from '$lib/types';

	export let user: User | null = null;

	async function handleLogout() {
		try {
			await api.post('/api/auth/logout');
			goto('/login');
		} catch (error) {
			toasts.show('Logout failed: ' + (error as Error).message, 'error');
		}
	}

	$: currentPath = $page.url.pathname;
</script>

<nav class="nav-bar">
	<div class="container">
		<div class="flex items-center justify-between h-16">
			<div class="flex items-center space-x-8">
				<h1 class="text-xl font-bold text-gray-900">Task Manager</h1>
				{#if user}
					<div class="flex space-x-4">
						<a href="/" class="nav-link" class:active={currentPath === '/'}>Todos</a>
						<a href="/projects" class="nav-link" class:active={currentPath === '/projects'}
							>Projects</a
						>
						<a
							href="/oauth-clients"
							class="nav-link"
							class:active={currentPath === '/oauth-clients'}>OAuth Clients</a
						>
						<a href="/trash" class="nav-link" class:active={currentPath === '/trash'}>Trash</a>
					</div>
				{/if}
			</div>

			<div class="flex items-center space-x-4">
				{#if user}
					<span class="text-sm text-gray-600">Welcome, {user.username}</span>
					<button
						class="btn btn-outline text-sm"
						on:click={handleLogout}
						data-testid="logout-button">Logout</button
					>
				{/if}
				<ThemeToggle />
			</div>
		</div>
	</div>
</nav>
