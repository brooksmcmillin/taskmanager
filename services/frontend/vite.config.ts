import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import fs from 'fs';
import path from 'path';

export default defineConfig({
	plugins: [sveltekit()],
	server: {
		host: '0.0.0.0',
		port: 3000,
		allowedHosts: ['todo-stage.brooksmcmillin.com'],
		https: {
			key: fs.readFileSync(path.resolve(__dirname, '.certs/key.pem')),
			cert: fs.readFileSync(path.resolve(__dirname, '.certs/cert.pem'))
		},
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
