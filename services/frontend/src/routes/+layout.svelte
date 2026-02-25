<script lang="ts">
	import '../app.scss';
	import Navigation from '$lib/components/Navigation.svelte';
	import Toasts from '$lib/components/Toasts.svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	export let data;

	// Redirect to login if not authenticated (client-side)
	onMount(() => {
		const publicRoutes = ['/login', '/register', '/oauth/authorize', '/privacy', '/terms'];
		const isPublicRoute = publicRoutes.some((route) => $page.url.pathname.startsWith(route));

		if (!data.user && !isPublicRoute) {
			goto(`/login?redirect=${encodeURIComponent($page.url.pathname)}`);
		}
	});

	// Hide navigation on OAuth consent page
	$: showNav = !$page.url.pathname.startsWith('/oauth/');
</script>

<svelte:head>
	<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</svelte:head>

{#if showNav}
	<Navigation user={data.user} />
{/if}
<slot />
<Toasts />
