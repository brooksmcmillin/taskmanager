import { marked } from 'marked';
import DOMPurify from 'dompurify';

/**
 * Extract [[Page Title]] references from markdown content.
 */
export function extractWikiLinks(content: string): string[] {
	const matches = content.match(/\[\[([^\]]+)\]\]/g);
	if (!matches) return [];
	return [...new Set(matches.map((m) => m.slice(2, -2).trim()))];
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
		const slug = resolvedSlugs[trimmed];
		if (slug) {
			return `<a href="/wiki/${encodeURIComponent(slug)}" class="wiki-link">${trimmed}</a>`;
		}
		// Missing page — link to create
		return `<a href="/wiki/new?title=${encodeURIComponent(trimmed)}" class="wiki-link wiki-link-missing">${trimmed}</a>`;
	});

	const html = marked.parse(withLinks, { async: false }) as string;
	return DOMPurify.sanitize(html, {
		ADD_ATTR: ['class'],
		ADD_TAGS: ['a']
	});
}
