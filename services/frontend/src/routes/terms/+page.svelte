<script lang="ts">
	const lastUpdated = 'February 16, 2026';
	const appName = 'TaskManager';
	const contactEmail = 'support@taskmanager.com';
</script>

<svelte:head>
	<title>Terms and Conditions - {appName}</title>
</svelte:head>

<main class="container legal-page">
	<div class="legal-content">
		<h1>Terms and Conditions</h1>
		<p class="last-updated">Last updated: {lastUpdated}</p>

		<section>
			<h2>1. Acceptance of Terms</h2>
			<p>
				By accessing or using {appName} (the "Service"), you agree to be bound by these Terms and Conditions
				("Terms"). If you do not agree to these Terms, do not use the Service.
			</p>
		</section>

		<section>
			<h2>2. Description of Service</h2>
			<p>
				{appName} is a task management application that allows users to create, organize, and track tasks
				and projects. The Service may include web-based interfaces, APIs, and related tools.
			</p>
		</section>

		<section>
			<h2>3. Account Registration</h2>
			<ul>
				<li>You must provide accurate and complete information when creating an account.</li>
				<li>You are responsible for maintaining the confidentiality of your login credentials.</li>
				<li>You are responsible for all activities that occur under your account.</li>
				<li>You must notify us immediately of any unauthorized use of your account.</li>
				<li>You must be at least 13 years of age to use the Service.</li>
			</ul>
		</section>

		<section>
			<h2>4. Acceptable Use</h2>
			<p>You agree not to:</p>
			<ul>
				<li>Use the Service for any unlawful purpose or in violation of any applicable laws.</li>
				<li>Attempt to gain unauthorized access to the Service or its related systems.</li>
				<li>Interfere with or disrupt the integrity or performance of the Service.</li>
				<li>Upload or transmit malicious code, viruses, or harmful data.</li>
				<li>Use the Service to harass, abuse, or harm others.</li>
				<li>Reverse engineer, decompile, or disassemble any part of the Service.</li>
				<li>Use automated means to access the Service without our express permission.</li>
				<li>Resell or redistribute the Service without authorization.</li>
			</ul>
		</section>

		<section>
			<h2>5. User Content</h2>
			<p>
				You retain ownership of all content you create within the Service, including tasks,
				projects, and notes ("User Content"). By using the Service, you grant us a limited license
				to store, process, and display your User Content solely for the purpose of providing the
				Service to you.
			</p>
			<p>
				You are solely responsible for your User Content. We do not endorse or assume liability for
				any User Content.
			</p>
		</section>

		<section>
			<h2>6. Text Message Communications</h2>
			<p>If you opt in to receive text message notifications:</p>
			<ul>
				<li>You consent to receive automated text messages related to the Service.</li>
				<li>Message frequency varies based on your account activity and settings.</li>
				<li>Message and data rates may apply.</li>
				<li>You may opt out at any time by replying STOP to any message.</li>
				<li>Reply HELP for assistance.</li>
				<li>Consent to receive texts is not required to use or purchase the Service.</li>
				<li>Your phone number will not be shared with third parties for marketing purposes.</li>
			</ul>
			<p>
				For more information, see our <a href="/privacy">Privacy Policy</a>.
			</p>
		</section>

		<section>
			<h2>7. Intellectual Property</h2>
			<p>
				The Service, including its design, features, code, and documentation, is owned by
				{appName} and protected by intellectual property laws. These Terms do not grant you any right
				to use our trademarks, logos, or branding without prior written consent.
			</p>
		</section>

		<section>
			<h2>8. Third-Party Services</h2>
			<p>
				The Service may integrate with third-party applications and services. We are not responsible
				for the availability, accuracy, or content of third-party services. Your use of third-party
				services is subject to their respective terms and policies.
			</p>
		</section>

		<section>
			<h2>9. Service Availability</h2>
			<p>
				We strive to maintain the availability of the Service but do not guarantee uninterrupted
				access. The Service may be temporarily unavailable due to maintenance, updates, or
				circumstances beyond our control. We are not liable for any downtime or data loss.
			</p>
		</section>

		<section>
			<h2>10. Termination</h2>
			<p>
				We reserve the right to suspend or terminate your account at any time for violation of these
				Terms or for any other reason at our discretion. You may terminate your account at any time
				by contacting us. Upon termination, your right to use the Service ceases immediately. We may
				retain certain data as required by law.
			</p>
		</section>

		<section>
			<h2>11. Disclaimer of Warranties</h2>
			<p>
				THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT WARRANTIES OF ANY KIND, EITHER
				EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO IMPLIED WARRANTIES OF MERCHANTABILITY,
				FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT. WE DO NOT WARRANT THAT THE SERVICE
				WILL BE UNINTERRUPTED, ERROR-FREE, OR SECURE.
			</p>
		</section>

		<section>
			<h2>12. Limitation of Liability</h2>
			<p>
				TO THE MAXIMUM EXTENT PERMITTED BY LAW, {appName.toUpperCase()} SHALL NOT BE LIABLE FOR ANY INDIRECT,
				INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, OR ANY LOSS OF PROFITS OR REVENUE, WHETHER
				INCURRED DIRECTLY OR INDIRECTLY, OR ANY LOSS OF DATA, USE, GOODWILL, OR OTHER INTANGIBLE LOSSES,
				RESULTING FROM YOUR USE OF THE SERVICE.
			</p>
		</section>

		<section>
			<h2>13. Indemnification</h2>
			<p>
				You agree to indemnify and hold harmless {appName}, its officers, directors, employees, and
				agents from any claims, damages, losses, liabilities, and expenses (including attorneys'
				fees) arising out of or related to your use of the Service or violation of these Terms.
			</p>
		</section>

		<section>
			<h2>14. Changes to Terms</h2>
			<p>
				We may modify these Terms at any time. We will notify you of material changes by posting the
				updated Terms on this page and updating the "Last updated" date. Your continued use of the
				Service after changes constitutes acceptance of the revised Terms.
			</p>
		</section>

		<section>
			<h2>15. Governing Law</h2>
			<p>
				These Terms shall be governed by and construed in accordance with the laws of the
				jurisdiction in which {appName} operates, without regard to its conflict of law provisions.
			</p>
		</section>

		<section>
			<h2>16. Contact Us</h2>
			<p>
				If you have questions about these Terms and Conditions, please contact us at
				<a href="mailto:{contactEmail}">{contactEmail}</a>.
			</p>
		</section>
	</div>
</main>

<style>
	.legal-page {
		max-width: 720px;
		margin: 2rem auto;
		padding-bottom: 4rem;
	}

	.legal-content {
		line-height: 1.7;
	}

	h1 {
		font-size: 2rem;
		margin-bottom: 0.25rem;
	}

	.last-updated {
		color: var(--text-muted);
		font-size: 0.875rem;
		margin-bottom: 2rem;
	}

	section {
		margin-bottom: 2rem;
	}

	h2 {
		font-size: 1.25rem;
		margin-bottom: 0.75rem;
		padding-top: 0.5rem;
	}

	p {
		margin-bottom: 0.75rem;
		color: var(--text-secondary);
	}

	ul {
		margin: 0.5rem 0 1rem 1.5rem;
		color: var(--text-secondary);
	}

	li {
		margin-bottom: 0.375rem;
	}

	a {
		color: var(--primary-color);
	}

	a:hover {
		text-decoration: underline;
	}
</style>
