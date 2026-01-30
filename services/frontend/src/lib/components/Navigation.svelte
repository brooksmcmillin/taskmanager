<script lang="ts">
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import ThemeToggle from './ThemeToggle.svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { User } from '$lib/types';

	let { user = null }: { user: User | null } = $props();

	let newsDropdownOpen = $state(false);
	let tasksDropdownOpen = $state(false);
	let userDropdownOpen = $state(false);
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

	function openTasksDropdown() {
		if (closeTimeout) {
			clearTimeout(closeTimeout);
			closeTimeout = null;
		}
		tasksDropdownOpen = true;
	}

	function scheduleCloseTasksDropdown() {
		closeTimeout = setTimeout(() => {
			tasksDropdownOpen = false;
			closeTimeout = null;
		}, 200);
	}

	function openUserDropdown() {
		if (closeTimeout) {
			clearTimeout(closeTimeout);
			closeTimeout = null;
		}
		userDropdownOpen = true;
	}

	function scheduleCloseUserDropdown() {
		closeTimeout = setTimeout(() => {
			userDropdownOpen = false;
			closeTimeout = null;
		}, 200);
	}

	function closeDropdowns() {
		newsDropdownOpen = false;
		tasksDropdownOpen = false;
		userDropdownOpen = false;
		if (closeTimeout) {
			clearTimeout(closeTimeout);
			closeTimeout = null;
		}
	}

	let currentPath = $derived($page.url.pathname);
	let isNewsActive = $derived(currentPath.startsWith('/news'));
	let isTasksActive = $derived(
		currentPath === '/' ||
			currentPath.startsWith('/projects') ||
			currentPath.startsWith('/recurring-tasks')
	);
</script>

<nav class="nav-bar">
	<div class="container">
		<div class="flex items-center justify-between h-16">
			<div class="flex items-center space-x-8">
				<h1 class="text-xl font-bold text-gray-900">Task Manager</h1>
				{#if user}
					<div class="flex space-x-4">
						<!-- Tasks Dropdown -->
						<div
							class="nav-dropdown"
							onmouseenter={openTasksDropdown}
							onmouseleave={scheduleCloseTasksDropdown}
						>
							<span
								class="nav-link nav-dropdown-trigger"
								class:active={isTasksActive}
								onclick={() => (tasksDropdownOpen = !tasksDropdownOpen)}
								role="button"
								tabindex="0"
								aria-expanded={tasksDropdownOpen}
								aria-haspopup="true"
							>
								Tasks
								<svg
									class="dropdown-arrow"
									class:open={tasksDropdownOpen}
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
							{#if tasksDropdownOpen}
								<div class="dropdown-menu">
									<a
										href="/"
										class="dropdown-item"
										class:active={currentPath === '/'}
										onclick={closeDropdowns}
									>
										Todos
									</a>
									<a
										href="/projects"
										class="dropdown-item"
										class:active={currentPath === '/projects'}
										onclick={closeDropdowns}
									>
										Projects
									</a>
									<a
										href="/recurring-tasks"
										class="dropdown-item"
										class:active={currentPath === '/recurring-tasks'}
										onclick={closeDropdowns}
									>
										Recurring
									</a>
								</div>
							{/if}
						</div>

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

						<a href="/trash" class="nav-link" class:active={currentPath === '/trash'}>Trash</a>
					</div>
				{/if}
			</div>

			<div class="flex items-center space-x-4">
				{#if user}
					<!-- User Dropdown -->
					<div
						class="nav-dropdown user-dropdown"
						onmouseenter={openUserDropdown}
						onmouseleave={scheduleCloseUserDropdown}
					>
						<button
							class="user-dropdown-trigger"
							onclick={() => (userDropdownOpen = !userDropdownOpen)}
							aria-expanded={userDropdownOpen}
							aria-haspopup="true"
							aria-label="User menu"
						>
							<svg
								class="user-icon"
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="currentColor"
							>
								<path
									fill-rule="evenodd"
									d="M18.685 19.097A9.723 9.723 0 0021.75 12c0-5.385-4.365-9.75-9.75-9.75S2.25 6.615 2.25 12a9.723 9.723 0 003.065 7.097A9.716 9.716 0 0012 21.75a9.716 9.716 0 006.685-2.653zm-12.54-1.285A7.486 7.486 0 0112 15a7.486 7.486 0 015.855 2.812A8.224 8.224 0 0112 20.25a8.224 8.224 0 01-5.855-2.438zM15.75 9a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0z"
									clip-rule="evenodd"
								/>
							</svg>
						</button>
						{#if userDropdownOpen}
							<div class="dropdown-menu dropdown-menu-right">
								<div class="dropdown-header">
									<span class="text-sm font-semibold">{user.username}</span>
								</div>
								<div class="dropdown-divider"></div>
								<a
									href="/oauth-clients"
									class="dropdown-item"
									class:active={currentPath === '/oauth-clients'}
									onclick={closeDropdowns}
								>
									OAuth Clients
								</a>
								{#if user.is_admin}
									<a
										href="/admin/registration-codes"
										class="dropdown-item"
										class:active={currentPath === '/admin/registration-codes'}
										onclick={closeDropdowns}
									>
										Registration Codes
									</a>
								{/if}
								<div class="dropdown-divider"></div>
								<button
									class="dropdown-item dropdown-logout"
									onclick={() => {
										closeDropdowns();
										handleLogout();
									}}
									data-testid="logout-button"
								>
									Logout
								</button>
							</div>
						{/if}
					</div>
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
		background-color: var(--dropdown-bg);
		border-radius: 0.5rem;
		box-shadow: var(--shadow-lg);
		border: 1px solid var(--border-color);
		overflow: hidden;
		z-index: 50;
		animation: slideDown 0.15s ease-out;
	}

	.dropdown-menu-right {
		left: auto;
		right: 0;
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
		color: var(--text-secondary);
		text-decoration: none;
		transition: background-color var(--transition-fast);
	}

	.dropdown-item:hover {
		background-color: var(--bg-hover);
	}

	.dropdown-item.active {
		background-color: var(--primary-50);
		color: var(--primary-600);
		font-weight: 500;
	}

	.dropdown-logout {
		width: 100%;
		text-align: left;
		border: none;
		background: none;
		cursor: pointer;
		font-family: inherit;
	}

	.dropdown-header {
		padding: 0.75rem 1rem 0.5rem 1rem;
		color: var(--text-primary);
		font-size: 0.875rem;
	}

	.dropdown-divider {
		height: 1px;
		margin: 0.25rem 0;
		background-color: var(--border-color);
	}

	.user-dropdown {
		position: relative;
	}

	.user-dropdown-trigger {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: 0.5rem;
		border: none;
		background: none;
		cursor: pointer;
		border-radius: 9999px;
		transition: background-color var(--transition-fast);
		color: var(--text-muted);
	}

	.user-dropdown-trigger:hover {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}

	.user-icon {
		width: 1.75rem;
		height: 1.75rem;
	}
</style>
