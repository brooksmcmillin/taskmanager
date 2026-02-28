<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { slide } from 'svelte/transition';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import ThemeToggle from './ThemeToggle.svelte';
	import { api } from '$lib/api/client';
	import { toasts } from '$lib/stores/ui';
	import type { User } from '$lib/types';

	// Must match $breakpoint-md in app.scss
	const MOBILE_BREAKPOINT = 768;

	let { user = null }: { user: User | null } = $props();

	let newsDropdownOpen = $state(false);
	let tasksDropdownOpen = $state(false);
	let userDropdownOpen = $state(false);
	let mobileMenuOpen = $state(false);
	let closeTimeout: ReturnType<typeof setTimeout> | null = null;
	let hamburgerBtnRef: HTMLButtonElement | undefined = $state(undefined);
	let mobileMenuRef: HTMLDivElement | undefined = $state(undefined);

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

	function toggleUserDropdown() {
		userDropdownOpen = !userDropdownOpen;
	}

	function closeAllMenus() {
		newsDropdownOpen = false;
		tasksDropdownOpen = false;
		userDropdownOpen = false;
		mobileMenuOpen = false;
		if (closeTimeout) {
			clearTimeout(closeTimeout);
			closeTimeout = null;
		}
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

	async function toggleMobileMenu() {
		mobileMenuOpen = !mobileMenuOpen;
		if (!mobileMenuOpen) {
			closeDropdowns();
		} else {
			// Wait for Svelte to render the menu DOM before focusing
			await tick();
			const firstItem = mobileMenuRef?.querySelector<HTMLElement>('a, button');
			firstItem?.focus();
		}
	}

	function closeMobileMenu() {
		mobileMenuOpen = false;
		closeDropdowns();
		// Return focus to the hamburger button
		hamburgerBtnRef?.focus();
	}

	// Focus trap: keep Tab cycling within the mobile menu
	function handleMobileMenuKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			closeMobileMenu();
			return;
		}

		if (event.key !== 'Tab' || !mobileMenuRef) return;

		const focusable = mobileMenuRef.querySelectorAll<HTMLElement>(
			'a[href], button:not([disabled])'
		);
		if (focusable.length === 0) return;

		const first = focusable[0];
		const last = focusable[focusable.length - 1];

		if (event.shiftKey && document.activeElement === first) {
			event.preventDefault();
			last.focus();
		} else if (!event.shiftKey && document.activeElement === last) {
			event.preventDefault();
			first.focus();
		}
	}

	// Close mobile menu when resizing past breakpoint (issue #1)
	function handleResize() {
		if (window.innerWidth > MOBILE_BREAKPOINT && mobileMenuOpen) {
			closeAllMenus();
		}
	}

	// Body scroll lock when mobile menu is open (issue #3)
	$effect(() => {
		if (mobileMenuOpen) {
			document.body.style.overflow = 'hidden';
		} else {
			document.body.style.overflow = '';
		}
	});

	// Close user dropdown on outside click (since it's click-only, not hover)
	function handleDocumentClick(event: MouseEvent) {
		if (!userDropdownOpen) return;
		const target = event.target as HTMLElement;
		if (!target.closest('.user-dropdown')) {
			userDropdownOpen = false;
		}
	}

	onMount(() => {
		window.addEventListener('resize', handleResize);
		document.addEventListener('click', handleDocumentClick);
		return () => {
			window.removeEventListener('resize', handleResize);
			document.removeEventListener('click', handleDocumentClick);
			// Ensure scroll is restored on unmount
			document.body.style.overflow = '';
		};
	});

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

				<!-- Desktop Navigation -->
				{#if user}
					<div class="desktop-nav flex space-x-4">
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

						<a href="/wiki" class="nav-link" class:active={currentPath.startsWith('/wiki')}>Wiki</a>
						<a href="/snippets" class="nav-link" class:active={currentPath.startsWith('/snippets')}>Snippets</a>
						<a href="/trash" class="nav-link" class:active={currentPath === '/trash'}>Trash</a>
					</div>
				{/if}
			</div>

			<div class="flex items-center space-x-4">
				{#if user}
					<!-- Desktop User Dropdown -->
					<div class="nav-dropdown user-dropdown desktop-nav">
						<button
							class="user-dropdown-trigger"
							onclick={toggleUserDropdown}
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
									<span class="text-sm font-semibold">{user.email}</span>
								</div>
								<div class="dropdown-divider"></div>
								<a
									href="/settings"
									class="dropdown-item"
									class:active={currentPath === '/settings'}
									onclick={closeDropdowns}
								>
									Settings
								</a>
								<a
									href="/oauth-clients"
									class="dropdown-item"
									class:active={currentPath === '/oauth-clients'}
									onclick={closeDropdowns}
								>
									OAuth Clients
								</a>
								<a
									href="/api-keys"
									class="dropdown-item"
									class:active={currentPath === '/api-keys'}
									onclick={closeDropdowns}
								>
									API Keys
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
									<a
										href="/admin/loki"
										class="dropdown-item"
										class:active={currentPath === '/admin/loki'}
										onclick={closeDropdowns}
									>
										Log Ingestion
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

					<!-- Mobile Hamburger Button -->
					<button
						class="mobile-menu-btn"
						bind:this={hamburgerBtnRef}
						onclick={toggleMobileMenu}
						aria-label="Toggle menu"
						aria-expanded={mobileMenuOpen}
					>
						{#if mobileMenuOpen}
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<line x1="18" y1="6" x2="6" y2="18"></line>
								<line x1="6" y1="6" x2="18" y2="18"></line>
							</svg>
						{:else}
							<svg
								xmlns="http://www.w3.org/2000/svg"
								viewBox="0 0 24 24"
								fill="none"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
								stroke-linejoin="round"
							>
								<line x1="3" y1="12" x2="21" y2="12"></line>
								<line x1="3" y1="6" x2="21" y2="6"></line>
								<line x1="3" y1="18" x2="21" y2="18"></line>
							</svg>
						{/if}
					</button>
				{/if}
				<ThemeToggle />
			</div>
		</div>
	</div>

	<!-- Screen reader announcement for menu state -->
	<div class="sr-only" aria-live="polite">
		{#if mobileMenuOpen}Navigation menu opened{/if}
	</div>

	<!-- Mobile Menu Drawer -->
	{#if user && mobileMenuOpen}
		<div class="mobile-menu-backdrop" onclick={closeMobileMenu} role="presentation"></div>
		<!-- svelte-ignore a11y_no_static_element_interactions -->
		<div
			class="mobile-menu"
			bind:this={mobileMenuRef}
			onkeydown={handleMobileMenuKeydown}
			role="navigation"
			aria-label="Mobile navigation"
			transition:slide={{ duration: 200 }}
		>
			<div class="mobile-menu-section">
				<div class="mobile-menu-label">Tasks</div>
				<a
					href="/"
					class="mobile-menu-item"
					class:active={currentPath === '/'}
					onclick={closeMobileMenu}
				>
					Todos
				</a>
				<a
					href="/projects"
					class="mobile-menu-item"
					class:active={currentPath === '/projects'}
					onclick={closeMobileMenu}
				>
					Projects
				</a>
				<a
					href="/recurring-tasks"
					class="mobile-menu-item"
					class:active={currentPath === '/recurring-tasks'}
					onclick={closeMobileMenu}
				>
					Recurring
				</a>
			</div>

			<div class="mobile-menu-section">
				<div class="mobile-menu-label">News</div>
				<a
					href="/news"
					class="mobile-menu-item"
					class:active={currentPath === '/news'}
					onclick={closeMobileMenu}
				>
					Feed
				</a>
				<a
					href="/news/sources"
					class="mobile-menu-item"
					class:active={currentPath === '/news/sources'}
					onclick={closeMobileMenu}
				>
					Sources
				</a>
			</div>

			<div class="mobile-menu-section">
				<div class="mobile-menu-label">Wiki</div>
				<a
					href="/wiki"
					class="mobile-menu-item"
					class:active={currentPath.startsWith('/wiki')}
					onclick={closeMobileMenu}
				>
					Wiki Pages
				</a>
			</div>

			<div class="mobile-menu-section">
				<div class="mobile-menu-label">Snippets</div>
				<a
					href="/snippets"
					class="mobile-menu-item"
					class:active={currentPath.startsWith('/snippets')}
					onclick={closeMobileMenu}
				>
					All Snippets
				</a>
			</div>

			<div class="mobile-menu-section">
				<a
					href="/trash"
					class="mobile-menu-item"
					class:active={currentPath === '/trash'}
					onclick={closeMobileMenu}
				>
					Trash
				</a>
			</div>

			<div class="mobile-menu-divider"></div>

			<div class="mobile-menu-section">
				<!-- Email is validated by Pydantic EmailStr on backend; Svelte auto-escapes output -->
				<div class="mobile-menu-label">{user.email}</div>
				<a
					href="/settings"
					class="mobile-menu-item"
					class:active={currentPath === '/settings'}
					onclick={closeMobileMenu}
				>
					Settings
				</a>
				<a
					href="/oauth-clients"
					class="mobile-menu-item"
					class:active={currentPath === '/oauth-clients'}
					onclick={closeMobileMenu}
				>
					OAuth Clients
				</a>
				<a
					href="/api-keys"
					class="mobile-menu-item"
					class:active={currentPath === '/api-keys'}
					onclick={closeMobileMenu}
				>
					API Keys
				</a>
				{#if user.is_admin}
					<a
						href="/admin/registration-codes"
						class="mobile-menu-item"
						class:active={currentPath === '/admin/registration-codes'}
						onclick={closeMobileMenu}
					>
						Registration Codes
					</a>
					<a
						href="/admin/loki"
						class="mobile-menu-item"
						class:active={currentPath === '/admin/loki'}
						onclick={closeMobileMenu}
					>
						Log Ingestion
					</a>
				{/if}
				<button
					class="mobile-menu-item mobile-logout-btn"
					onclick={() => {
						closeMobileMenu();
						handleLogout();
					}}
					data-testid="mobile-logout-button"
				>
					Logout
				</button>
			</div>
		</div>
	{/if}
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
		border-radius: var(--radius-lg);
		box-shadow: var(--shadow-lg);
		border: 1px solid var(--border-color);
		overflow: hidden;
		z-index: 50;
		animation: slideDown 0.2s ease-out;
	}

	.dropdown-menu-right {
		left: auto;
		right: 0;
	}

	@keyframes slideDown {
		from {
			opacity: 0;
			transform: translateY(-0.375rem);
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
		transition: all var(--transition-fast);
	}

	.dropdown-item:hover {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}

	.dropdown-item.active {
		background-color: var(--primary-50);
		color: var(--primary-600);
		font-weight: 600;
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

	/* Mobile hamburger button - hidden on desktop */
	.mobile-menu-btn {
		display: none;
		align-items: center;
		justify-content: center;
		width: 2.5rem;
		height: 2.5rem;
		padding: 0.375rem;
		border: none;
		background: none;
		cursor: pointer;
		border-radius: var(--radius);
		color: var(--text-secondary);
		transition: all var(--transition-fast);
	}

	.mobile-menu-btn:hover {
		background-color: var(--bg-hover);
		color: var(--text-primary);
	}

	.mobile-menu-btn svg {
		width: 1.5rem;
		height: 1.5rem;
	}

	/* Mobile menu backdrop */
	.mobile-menu-backdrop {
		display: none;
		position: fixed;
		top: 4rem;
		left: 0;
		right: 0;
		bottom: 0;
		background-color: var(--bg-overlay);
		z-index: 40;
	}

	/* Screen reader only - visually hidden but accessible */
	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border-width: 0;
	}

	/* Mobile slide-down menu (open/close animated via Svelte transition:slide) */
	.mobile-menu {
		display: none;
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		background-color: var(--bg-card);
		border-bottom: 1px solid var(--border-color);
		box-shadow: var(--shadow-lg);
		z-index: 50;
		max-height: calc(100vh - 4rem);
		overflow-y: auto;
	}

	.mobile-menu-section {
		padding: 0.5rem 0;
	}

	.mobile-menu-label {
		padding: 0.5rem 1.25rem;
		font-size: 0.6875rem;
		font-weight: 700;
		color: var(--text-muted);
		text-transform: uppercase;
		letter-spacing: 0.08em;
	}

	.mobile-menu-item {
		display: block;
		padding: 0.75rem 1.25rem;
		font-size: 0.9375rem;
		color: var(--text-secondary);
		text-decoration: none;
		transition: background-color var(--transition-fast);
	}

	.mobile-menu-item:hover {
		background-color: var(--bg-hover);
		text-decoration: none;
	}

	.mobile-menu-item.active {
		background-color: var(--primary-50);
		color: var(--primary-600);
		font-weight: 500;
	}

	.mobile-logout-btn {
		width: 100%;
		text-align: left;
		border: none;
		background: none;
		cursor: pointer;
		font-family: inherit;
		color: var(--error-600);
	}

	.mobile-menu-divider {
		height: 1px;
		margin: 0.25rem 1rem;
		background-color: var(--border-color);
	}

	/* Show mobile elements / hide desktop elements on small screens */
	@media (max-width: 768px) {
		/* $breakpoint-md */
		.desktop-nav {
			display: none !important;
		}

		.mobile-menu-btn {
			display: flex;
		}

		.mobile-menu-backdrop {
			display: block;
		}

		.mobile-menu {
			display: block;
		}
	}
</style>
