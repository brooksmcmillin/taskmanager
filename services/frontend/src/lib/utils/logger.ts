/**
 * Centralized logging utility with proper levels and configuration.
 *
 * Usage:
 *   import { logger } from '$lib/utils/logger';
 *   logger.error('Failed to load todos:', error);
 *   logger.warn('Unexpected response format');
 *   logger.info('User logged in');
 *   logger.debug('API response:', data);
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogConfig {
	minLevel: LogLevel;
	enableInProduction: boolean;
}

const config: LogConfig = {
	minLevel: import.meta.env.PROD ? 'warn' : 'debug',
	enableInProduction: false
};

const levels: Record<LogLevel, number> = {
	debug: 0,
	info: 1,
	warn: 2,
	error: 3
};

function shouldLog(level: LogLevel): boolean {
	if (import.meta.env.PROD && !config.enableInProduction) {
		return level === 'error' || level === 'warn';
	}
	return levels[level] >= levels[config.minLevel];
}

export const logger = {
	debug: (message: string, ...args: unknown[]) => {
		if (shouldLog('debug')) console.debug(`[DEBUG] ${message}`, ...args);
	},
	info: (message: string, ...args: unknown[]) => {
		if (shouldLog('info')) console.info(`[INFO] ${message}`, ...args);
	},
	warn: (message: string, ...args: unknown[]) => {
		if (shouldLog('warn')) console.warn(`[WARN] ${message}`, ...args);
	},
	error: (message: string, ...args: unknown[]) => {
		if (shouldLog('error')) console.error(`[ERROR] ${message}`, ...args);
	}
};
