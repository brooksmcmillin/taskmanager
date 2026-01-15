<script lang="ts">
	import '../app.scss';
	import Navigation from '$lib/components/Navigation.svelte';
	import { page } from '$app/stores';
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';

	export let data;

	// Redirect to login if not authenticated (client-side)
	onMount(() => {
		const publicRoutes = ['/login', '/register'];
		const isPublicRoute = publicRoutes.includes($page.url.pathname);

		if (!data.user && !isPublicRoute) {
			goto(`/login?redirect=${encodeURIComponent($page.url.pathname)}`);
		}
	});
</script>

<Navigation user={data.user} />
<slot />
