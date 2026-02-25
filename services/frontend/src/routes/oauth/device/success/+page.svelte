<script lang="ts">
	import OAuthResultCard from '$lib/components/OAuthResultCard.svelte';
</script>

<svelte:head>
	<title>Device Authorized</title>
</svelte:head>

<OAuthResultCard
	icon="✅"
	title="Device Authorized Successfully"
	message="Your device has been authorized. You can now close this window and return to your device."
	titleColor="success"
/>
