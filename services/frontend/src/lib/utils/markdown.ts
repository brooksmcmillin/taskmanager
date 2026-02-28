import { marked } from 'marked';
import DOMPurify from 'dompurify';

/**
 * Strip HTML tags and decode entities, returning plain text.
 * Useful for displaying RSS feed summaries as plain text.
 */
export function stripHtml(html: string): string {
	const clean = DOMPurify.sanitize(html, { ALLOWED_TAGS: [] });
	// DOMPurify with no allowed tags strips all elements, leaving text content.
	// Collapse whitespace runs (from removed block elements) into single spaces.
	return clean.replace(/\s+/g, ' ').trim();
}

/**
 * Extract [[Page Title]] references from markdown content.
 */
export function extractWikiLinks(content: string): string[] {
	const matches = content.match(/\[\[([^\]]+)\]\]/g);
	if (!matches) return [];
	return [...new Set(matches.map((m) => m.slice(2, -2).trim()))];
}

function escapeHtml(s: string): string {
	return s
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;');
}

/**
 * Render markdown content with wiki-link support.
 *
 * @param content - Raw markdown text
 * @param resolvedSlugs - Map of page title → slug (null = page doesn't exist)
 * @returns Sanitized HTML string
 */
export function renderMarkdown(
	content: string,
	resolvedSlugs: Record<string, string | null> = {}
): string {
	// Replace [[Page Title]] with links before markdown parsing
	const withLinks = content.replace(/\[\[([^\]]+)\]\]/g, (_match, title: string) => {
		const trimmed = title.trim();
		const escaped = escapeHtml(trimmed);
		const slug = resolvedSlugs[trimmed];
		if (slug) {
			return `<a href="/wiki/${encodeURIComponent(slug)}" class="wiki-link">${escaped}</a>`;
		}
		// Missing page — link to create
		return `<a href="/wiki/new?title=${encodeURIComponent(trimmed)}" class="wiki-link wiki-link-missing">${escaped}</a>`;
	});

	const html = marked.parse(withLinks, { async: false }) as string;
	return DOMPurify.sanitize(html, {
		ADD_ATTR: ['class'],
		ADD_TAGS: ['a']
	});
}
