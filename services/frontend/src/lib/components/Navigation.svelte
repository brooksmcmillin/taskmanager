<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import ThemeToggle from './ThemeToggle.svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { User } from '$lib/types';

	let { user = null }: { user: User | null } = $props();

	let newsDropdownOpen = $state(false);
	let closeTimeout: ReturnType<typeof setTimeout> | null = null;

	async function handleLogout() {
		try {
			await api.post('/api/auth/logout');
			goto('/login');
		} catch (error) {
			toasts.show('Logout failed: ' + (error as Error).message, 'error');
		}
	}

	function openNewsDropdown() {
		if (closeTimeout) {
			clearTimeout(closeTimeout);
			closeTimeout = null;
		}
		newsDropdownOpen = true;
	}

	function scheduleCloseNewsDropdown() {
		closeTimeout = setTimeout(() => {
			newsDropdownOpen = false;
			closeTimeout = null;
		}, 200);
	}

	function closeDropdowns() {
		newsDropdownOpen = false;
		if (closeTimeout) {
			clearTimeout(closeTimeout);
			closeTimeout = null;
		}
	}

	let currentPath = $derived($page.url.pathname);
	let isNewsActive = $derived(currentPath.startsWith('/news'));
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

						<!-- News Dropdown -->
						<div
							class="nav-dropdown"
							onmouseenter={openNewsDropdown}
							onmouseleave={scheduleCloseNewsDropdown}
						>
							<span
								class="nav-link nav-dropdown-trigger"
								class:active={isNewsActive}
								onclick={() => (newsDropdownOpen = !newsDropdownOpen)}
								role="button"
								tabindex="0"
								aria-expanded={newsDropdownOpen}
								aria-haspopup="true"
							>
								News
								<svg
									class="dropdown-arrow"
									class:open={newsDropdownOpen}
									xmlns="http://www.w3.org/2000/svg"
									viewBox="0 0 20 20"
									fill="currentColor"
								>
									<path
										fill-rule="evenodd"
										d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
										clip-rule="evenodd"
									/>
								</svg>
							</span>
							{#if newsDropdownOpen}
								<div class="dropdown-menu">
									<a
										href="/news"
										class="dropdown-item"
										class:active={currentPath === '/news'}
										onclick={closeDropdowns}
									>
										Feed
									</a>
									<a
										href="/news/sources"
										class="dropdown-item"
										class:active={currentPath === '/news/sources'}
										onclick={closeDropdowns}
									>
										Sources
									</a>
								</div>
							{/if}
						</div>

						<a
							href="/oauth-clients"
							class="nav-link"
							class:active={currentPath === '/oauth-clients'}>OAuth Clients</a
						>
						<a href="/trash" class="nav-link" class:active={currentPath === '/trash'}>Trash</a>
						{#if user.is_admin}
							<a
								href="/admin/registration-codes"
								class="nav-link"
								class:active={currentPath === '/admin/registration-codes'}>Registration Codes</a
							>
						{/if}
					</div>
				{/if}
			</div>

			<div class="flex items-center space-x-4">
				{#if user}
					<span class="text-sm text-gray-600">Welcome, {user.username}</span>
					<button class="btn btn-outline text-sm" onclick={handleLogout} data-testid="logout-button"
						>Logout</button
					>
				{/if}
				<ThemeToggle />
			</div>
		</div>
	</div>
</nav>

<style>
	.nav-dropdown {
		position: relative;
		display: inline-block;
	}

	.nav-dropdown-trigger {
		display: inline-flex;
		align-items: center;
		cursor: pointer;
		user-select: none;
	}

	.dropdown-arrow {
		display: inline-block;
		width: 1rem;
		height: 1rem;
		margin-left: 0.25rem;
		transition: transform 0.2s ease-in-out;
		flex-shrink: 0;
	}

	.dropdown-arrow.open {
		transform: rotate(180deg);
	}

	.dropdown-menu {
		position: absolute;
		top: 100%;
		left: 0;
		margin-top: 0.5rem;
		min-width: 10rem;
		background-color: white;
		border-radius: 0.5rem;
		box-shadow:
			0 10px 15px -3px rgba(0, 0, 0, 0.1),
			0 4px 6px -2px rgba(0, 0, 0, 0.05);
		border: 1px solid #e5e7eb;
		overflow: hidden;
		z-index: 50;
		animation: slideDown 0.15s ease-out;
	}

	@keyframes slideDown {
		from {
			opacity: 0;
			transform: translateY(-0.5rem);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.dropdown-item {
		display: block;
		padding: 0.5rem 1rem;
		font-size: 0.875rem;
		color: #374151;
		text-decoration: none;
		transition: background-color 0.15s ease-in-out;
	}

	.dropdown-item:hover {
		background-color: #f3f4f6;
	}

	.dropdown-item.active {
		background-color: #dbeafe;
		color: #2563eb;
		font-weight: 500;
	}

	/* Dark mode support */
	:global(.dark) .dropdown-menu {
		background-color: #1f2937;
		border-color: #374151;
	}

	:global(.dark) .dropdown-item {
		color: #d1d5db;
	}

	:global(.dark) .dropdown-item:hover {
		background-color: #374151;
	}

	:global(.dark) .dropdown-item.active {
		background-color: #1e3a8a;
		color: #60a5fa;
	}
</style>
