<script lang="ts">
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';

	let currentTheme = 'light';

	function toggleTheme() {
		const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
		currentTheme = newTheme;

		if (browser) {
			document.documentElement.setAttribute('data-theme', newTheme);
			localStorage.setItem('theme', newTheme);
		}
	}

	onMount(() => {
		// Load theme from localStorage (with SSR safety check)
		const savedTheme =
			typeof localStorage !== 'undefined' ? localStorage.getItem('theme') : null;
		if (savedTheme) {
			currentTheme = savedTheme;
			document.documentElement.setAttribute('data-theme', savedTheme);
		} else {
			// Check system preference
			const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
			currentTheme = prefersDark ? 'dark' : 'light';
			document.documentElement.setAttribute('data-theme', currentTheme);
		}
	});
</script>

<button
	class="theme-toggle"
	type="button"
	aria-label="Toggle theme"
	title="Toggle theme"
	on:click={toggleTheme}
>
	<svg
		class="sun-icon"
		xmlns="http://www.w3.org/2000/svg"
		fill="none"
		viewBox="0 0 24 24"
		stroke="currentColor"
	>
		<path
			stroke-linecap="round"
			stroke-linejoin="round"
			stroke-width="2"
			d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
		/>
	</svg>
	<svg
		class="moon-icon"
		xmlns="http://www.w3.org/2000/svg"
		fill="none"
		viewBox="0 0 24 24"
		stroke="currentColor"
	>
		<path
			stroke-linecap="round"
			stroke-linejoin="round"
			stroke-width="2"
			d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
		/>
	</svg>
</button>

<style>
	.theme-toggle {
		position: relative;
	}

	.sun-icon,
	.moon-icon {
		position: absolute;
		transition:
			opacity 0.2s ease,
			transform 0.2s ease;
	}

	/* Dark mode: show sun icon (to switch to light) */
	:global([data-theme='dark']) .sun-icon {
		opacity: 1;
		transform: rotate(0deg);
	}

	:global([data-theme='dark']) .moon-icon {
		opacity: 0;
		transform: rotate(-90deg);
	}

	/* Light mode: show moon icon (to switch to dark) */
	:global(:root:not([data-theme='dark'])) .sun-icon,
	:global([data-theme='light']) .sun-icon {
		opacity: 0;
		transform: rotate(90deg);
	}

	:global(:root:not([data-theme='dark'])) .moon-icon,
	:global([data-theme='light']) .moon-icon {
		opacity: 1;
		transform: rotate(0deg);
	}
</style>
