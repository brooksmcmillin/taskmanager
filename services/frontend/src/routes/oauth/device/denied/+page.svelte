<script lang="ts">
	import OAuthResultCard from '$lib/components/OAuthResultCard.svelte';
</script>

<svelte:head>
	<title>Device Authorization Denied</title>
</svelte:head>

<OAuthResultCard
	icon="❌"
	title="Device Authorization Denied"
	message="You have denied access to the device. The device will not be able to access your account."
	titleColor="error"
/>
