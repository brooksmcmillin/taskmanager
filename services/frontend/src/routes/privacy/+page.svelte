<script lang="ts">
	const lastUpdated = 'February 16, 2026';
	const appName = 'TaskManager';
	const contactEmail = 'privacy@taskmanager.com';
</script>

<svelte:head>
	<title>Privacy Policy - {appName}</title>
</svelte:head>

<main class="container legal-page">
	<div class="legal-content">
		<h1>Privacy Policy</h1>
		<p class="last-updated">Last updated: {lastUpdated}</p>

		<section>
			<h2>1. Introduction</h2>
			<p>
				{appName} ("we," "our," or "us") is committed to protecting your privacy. This Privacy Policy
				explains how we collect, use, disclose, and safeguard your information when you use our task management
				application and related services (the "Service").
			</p>
			<p>
				By using the Service, you agree to the collection and use of information in accordance with
				this policy.
			</p>
		</section>

		<section>
			<h2>2. Information We Collect</h2>

			<h3>2.1 Information You Provide</h3>
			<ul>
				<li><strong>Account Information:</strong> Email address and password when you register.</li>
				<li>
					<strong>Profile Information:</strong> Name and other optional details you choose to provide.
				</li>
				<li>
					<strong>Task Data:</strong> Tasks, projects, notes, due dates, and other content you create
					within the Service.
				</li>
				<li>
					<strong>Communications:</strong> Information you provide when contacting us for support.
				</li>
				<li>
					<strong>Phone Number:</strong> If you opt in to receive text message notifications, we collect
					your phone number.
				</li>
			</ul>

			<h3>2.2 Information Collected Automatically</h3>
			<ul>
				<li>
					<strong>Log Data:</strong> IP address, browser type, operating system, referring URLs, and access
					timestamps.
				</li>
				<li>
					<strong>Session Data:</strong> Session identifiers used to maintain your authenticated state.
				</li>
				<li>
					<strong>Usage Data:</strong> Features used, actions taken, and interactions with the Service.
				</li>
			</ul>
		</section>

		<section>
			<h2>3. How We Use Your Information</h2>
			<p>We use the information we collect to:</p>
			<ul>
				<li>Provide, maintain, and improve the Service.</li>
				<li>Authenticate your identity and manage your account.</li>
				<li>Send you notifications, updates, and administrative messages.</li>
				<li>Send text message notifications if you have opted in to receive them.</li>
				<li>Respond to your comments, questions, and support requests.</li>
				<li>Monitor and analyze usage trends to improve user experience.</li>
				<li>Detect, prevent, and address technical issues and security threats.</li>
				<li>Comply with legal obligations.</li>
			</ul>
		</section>

		<section>
			<h2>4. Text Message Communications</h2>
			<p>If you opt in to receive text messages from us, the following applies:</p>
			<ul>
				<li>
					You may receive notifications related to your tasks, reminders, and account updates.
				</li>
				<li>Message frequency varies based on your activity and preferences.</li>
				<li>Message and data rates may apply depending on your mobile carrier plan.</li>
				<li>You can opt out at any time by replying STOP to any message.</li>
				<li>Reply HELP for assistance.</li>
				<li>
					We will not share your phone number with third parties for their marketing purposes.
				</li>
				<li>
					Consent to receive text messages is not a condition of purchasing or using the Service.
				</li>
			</ul>
		</section>

		<section>
			<h2>5. Data Sharing and Disclosure</h2>
			<p>
				We do not sell your personal information. We may share your information in the following
				circumstances:
			</p>
			<ul>
				<li>
					<strong>Service Providers:</strong> With third-party vendors who assist us in operating the
					Service (e.g., hosting, analytics, SMS delivery), subject to confidentiality obligations.
				</li>
				<li>
					<strong>Legal Requirements:</strong> When required by law, regulation, legal process, or governmental
					request.
				</li>
				<li>
					<strong>Safety:</strong> To protect the rights, property, or safety of {appName}, our
					users, or others.
				</li>
				<li>
					<strong>Business Transfers:</strong> In connection with a merger, acquisition, or sale of assets,
					your information may be transferred.
				</li>
			</ul>
		</section>

		<section>
			<h2>6. Data Security</h2>
			<p>
				We implement appropriate technical and organizational security measures to protect your
				information, including encryption of data in transit and at rest, secure session management,
				and access controls. However, no method of transmission over the Internet or electronic
				storage is 100% secure.
			</p>
		</section>

		<section>
			<h2>7. Data Retention</h2>
			<p>
				We retain your information for as long as your account is active or as needed to provide the
				Service. You may request deletion of your account and associated data at any time by
				contacting us. We may retain certain information as required by law or for legitimate
				business purposes.
			</p>
		</section>

		<section>
			<h2>8. Your Rights</h2>
			<p>Depending on your jurisdiction, you may have the right to:</p>
			<ul>
				<li>Access the personal information we hold about you.</li>
				<li>Request correction of inaccurate information.</li>
				<li>Request deletion of your information.</li>
				<li>Object to or restrict processing of your information.</li>
				<li>Request a portable copy of your data.</li>
				<li>Withdraw consent at any time where processing is based on consent.</li>
			</ul>
			<p>
				To exercise these rights, contact us at <a href="mailto:{contactEmail}">{contactEmail}</a>.
			</p>
		</section>

		<section>
			<h2>9. Cookies and Tracking</h2>
			<p>
				We use session cookies to maintain your authenticated state. We do not use third-party
				tracking cookies or advertising cookies. Session cookies are deleted when you log out or
				when they expire.
			</p>
		</section>

		<section>
			<h2>10. Children's Privacy</h2>
			<p>
				The Service is not intended for children under the age of 13. We do not knowingly collect
				personal information from children under 13. If we become aware that we have collected
				information from a child under 13, we will take steps to delete it.
			</p>
		</section>

		<section>
			<h2>11. Changes to This Policy</h2>
			<p>
				We may update this Privacy Policy from time to time. We will notify you of any material
				changes by posting the new policy on this page and updating the "Last updated" date. Your
				continued use of the Service after changes constitutes acceptance of the updated policy.
			</p>
		</section>

		<section>
			<h2>12. Contact Us</h2>
			<p>
				If you have questions about this Privacy Policy, please contact us at
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

	h3 {
		font-size: 1.0625rem;
		margin-top: 1rem;
		margin-bottom: 0.5rem;
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
