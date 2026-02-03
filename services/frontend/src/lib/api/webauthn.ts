/**
 * WebAuthn utility functions for passkey authentication.
 */

import { api } from './client';

/**
 * Check if WebAuthn is supported in the current browser.
 */
export function isWebAuthnSupported(): boolean {
	return (
		typeof window !== 'undefined' &&
		window.PublicKeyCredential !== undefined &&
		typeof window.PublicKeyCredential === 'function'
	);
}

/**
 * Check if the platform supports conditional UI (autofill passkeys).
 */
export async function isConditionalUISupported(): Promise<boolean> {
	if (!isWebAuthnSupported()) return false;
	try {
		return (await PublicKeyCredential.isConditionalMediationAvailable?.()) ?? false;
	} catch {
		return false;
	}
}

/**
 * Convert a base64url string to an ArrayBuffer.
 */
function base64urlToBuffer(base64url: string): ArrayBuffer {
	// Add padding if needed
	const padding = '='.repeat((4 - (base64url.length % 4)) % 4);
	const base64 = base64url.replace(/-/g, '+').replace(/_/g, '/') + padding;
	const binary = atob(base64);
	const bytes = new Uint8Array(binary.length);
	for (let i = 0; i < binary.length; i++) {
		bytes[i] = binary.charCodeAt(i);
	}
	return bytes.buffer;
}

/**
 * Convert an ArrayBuffer to a base64url string.
 */
function bufferToBase64url(buffer: ArrayBuffer): string {
	const bytes = new Uint8Array(buffer);
	let binary = '';
	for (let i = 0; i < bytes.length; i++) {
		binary += String.fromCharCode(bytes[i]);
	}
	const base64 = btoa(binary);
	return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

/**
 * Parse server options into WebAuthn API format for registration.
 */
function parseCreationOptions(
	options: Record<string, unknown>
): PublicKeyCredentialCreationOptions {
	return {
		rp: options.rp as PublicKeyCredentialRpEntity,
		user: {
			...(options.user as Record<string, unknown>),
			id: base64urlToBuffer((options.user as Record<string, string>).id)
		} as PublicKeyCredentialUserEntity,
		challenge: base64urlToBuffer(options.challenge as string),
		pubKeyCredParams: options.pubKeyCredParams as PublicKeyCredentialParameters[],
		timeout: options.timeout as number,
		excludeCredentials: ((options.excludeCredentials as Array<Record<string, unknown>>) || []).map(
			(c) => ({
				type: c.type as PublicKeyCredentialType,
				id: base64urlToBuffer(c.id as string),
				transports: c.transports as AuthenticatorTransport[] | undefined
			})
		),
		authenticatorSelection: options.authenticatorSelection as AuthenticatorSelectionCriteria,
		attestation: options.attestation as AttestationConveyancePreference
	};
}

/**
 * Parse server options into WebAuthn API format for authentication.
 */
function parseRequestOptions(options: Record<string, unknown>): PublicKeyCredentialRequestOptions {
	return {
		challenge: base64urlToBuffer(options.challenge as string),
		timeout: options.timeout as number,
		rpId: options.rpId as string,
		allowCredentials: ((options.allowCredentials as Array<Record<string, unknown>>) || []).map(
			(c) => ({
				type: c.type as PublicKeyCredentialType,
				id: base64urlToBuffer(c.id as string),
				transports: c.transports as AuthenticatorTransport[] | undefined
			})
		),
		userVerification: options.userVerification as UserVerificationRequirement
	};
}

/**
 * Serialize a credential for sending to the server.
 */
function serializeCredential(credential: PublicKeyCredential): Record<string, unknown> {
	const response = credential.response as AuthenticatorAttestationResponse;

	const serialized: Record<string, unknown> = {
		id: credential.id,
		rawId: bufferToBase64url(credential.rawId),
		type: credential.type,
		response: {
			clientDataJSON: bufferToBase64url(response.clientDataJSON),
			attestationObject: bufferToBase64url(response.attestationObject)
		}
	};

	// Include transports if available
	if ('getTransports' in response && typeof response.getTransports === 'function') {
		(serialized.response as Record<string, unknown>).transports = response.getTransports();
	}

	return serialized;
}

/**
 * Serialize an assertion for sending to the server.
 */
function serializeAssertion(credential: PublicKeyCredential): Record<string, unknown> {
	const response = credential.response as AuthenticatorAssertionResponse;

	return {
		id: credential.id,
		rawId: bufferToBase64url(credential.rawId),
		type: credential.type,
		response: {
			clientDataJSON: bufferToBase64url(response.clientDataJSON),
			authenticatorData: bufferToBase64url(response.authenticatorData),
			signature: bufferToBase64url(response.signature),
			userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : null
		}
	};
}

export interface WebAuthnCredential {
	id: number;
	device_name: string | null;
	created_at: string;
	last_used_at: string | null;
}

/**
 * Register a new passkey for the current user.
 */
export async function registerPasskey(deviceName?: string): Promise<WebAuthnCredential> {
	if (!isWebAuthnSupported()) {
		throw new Error('WebAuthn is not supported in this browser');
	}

	// Get registration options from server
	const { challenge_id, options } = await api.post<{
		challenge_id: string;
		options: Record<string, unknown>;
	}>('/api/auth/webauthn/register/options', { device_name: deviceName });

	// Create credential using browser API
	const credential = (await navigator.credentials.create({
		publicKey: parseCreationOptions(options)
	})) as PublicKeyCredential;

	if (!credential) {
		throw new Error('Failed to create credential');
	}

	// Send credential to server for verification
	return api.post<WebAuthnCredential>('/api/auth/webauthn/register/verify', {
		challenge_id,
		credential: serializeCredential(credential),
		device_name: deviceName
	});
}

/**
 * Authenticate with a passkey.
 */
export async function authenticateWithPasskey(
	username?: string
): Promise<{ message: string; user: Record<string, unknown> }> {
	if (!isWebAuthnSupported()) {
		throw new Error('WebAuthn is not supported in this browser');
	}

	// Get authentication options from server
	const { challenge_id, options } = await api.post<{
		challenge_id: string;
		options: Record<string, unknown>;
	}>('/api/auth/webauthn/authenticate/options', { username });

	// Get assertion using browser API
	const assertion = (await navigator.credentials.get({
		publicKey: parseRequestOptions(options)
	})) as PublicKeyCredential;

	if (!assertion) {
		throw new Error('Failed to get assertion');
	}

	// Send assertion to server for verification
	return api.post<{ message: string; user: Record<string, unknown> }>(
		'/api/auth/webauthn/authenticate/verify',
		{
			challenge_id,
			credential: serializeAssertion(assertion)
		}
	);
}

/**
 * List all passkeys for the current user.
 */
export async function listPasskeys(): Promise<WebAuthnCredential[]> {
	const response = await api.get<{ data: WebAuthnCredential[]; meta: { count: number } }>(
		'/api/auth/webauthn/credentials'
	);
	return response.data;
}

/**
 * Delete a passkey.
 */
export async function deletePasskey(credentialId: number): Promise<void> {
	await api.delete(`/api/auth/webauthn/credentials/${credentialId}`);
}
