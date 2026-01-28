import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import fs from 'fs';
import path from 'path';

// Check if certificate files exist (for local dev with HTTPS)
const certsPath = path.resolve(__dirname, '.certs');
const keyPath = path.join(certsPath, 'key.pem');
const certPath = path.join(certsPath, 'cert.pem');
const hasCerts = fs.existsSync(keyPath) && fs.existsSync(certPath);

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		host: '0.0.0.0',
		port: 3000,
		allowedHosts: ['todo-stage.brooksmcmillin.com'],
		...(hasCerts && {
			https: {
				key: fs.readFileSync(keyPath),
				cert: fs.readFileSync(certPath)
			}
		}),
		proxy: {
			'/api': {
				target: process.env.VITE_API_URL || 'http://localhost:8000',
				changeOrigin: true,
				cookieDomainRewrite: '',
				secure: false,
				ws: true
			}
		}
	}
});
