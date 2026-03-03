<script lang="ts">
	import '../app.scss';
	import Navigation from '$lib/components/Navigation.svelte';
	import SearchModal from '$lib/components/SearchModal.svelte';
	import Toasts from '$lib/components/Toasts.svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { browser } from '$app/environment';
	import { connect, disconnect } from '$lib/services/eventStream';
	import { startEventHandlers, stopEventHandlers } from '$lib/services/eventHandlers';

	export let data;

	let searchOpen = false;

	function handleGlobalKeydown(event: KeyboardEvent) {
		if ((event.metaKey || event.ctrlKey) && event.key === 'k') {
			event.preventDefault();
			if (data.user) {
				searchOpen = true;
			}
		}
	}

	// Initialize theme on all pages (ThemeToggle only mounts when Navigation is visible)
	onMount(() => {
		if (browser) {
			const savedTheme = localStorage.getItem('theme');
			if (savedTheme) {
				document.documentElement.setAttribute('data-theme', savedTheme);
			} else {
				const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
				document.documentElement.setAttribute('data-theme', prefersDark ? 'dark' : 'light');
			}
		}

		const publicRoutes = ['/login', '/register', '/oauth/authorize', '/privacy', '/terms'];
		const isPublicRoute = publicRoutes.some((route) => $page.url.pathname.startsWith(route));

		if (!data.user && !isPublicRoute) {
			goto(`/login?redirect=${encodeURIComponent($page.url.pathname)}`);
		}

		// Start real-time event stream for authenticated users
		if (browser && data.user) {
			startEventHandlers();
			connect();
		}

		return () => {
			stopEventHandlers();
			disconnect();
		};
	});

	// Hide navigation on OAuth consent page
	$: showNav = !$page.url.pathname.startsWith('/oauth/');
</script>

<svelte:head>
	<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</svelte:head>

<svelte:window on:keydown={handleGlobalKeydown} />

{#if showNav}
	<Navigation user={data.user} />
{/if}
<slot />
<Toasts />

{#if data.user}
	<SearchModal bind:open={searchOpen} />
{/if}
