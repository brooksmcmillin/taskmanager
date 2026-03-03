import { marked, type Renderer } from 'marked';
import DOMPurify from 'dompurify';

// Custom renderer: open external links in new tab
const renderer: Partial<Renderer> = {
	link({ href, title, text }) {
		const titleAttr = title ? ` title="${escapeHtml(title)}"` : '';
		if (href && /^https?:\/\//.test(href)) {
			return `<a href="${escapeHtml(href)}"${titleAttr} target="_blank" rel="noopener noreferrer">${text}</a>`;
		}
		return `<a href="${escapeHtml(href ?? '')}"${titleAttr}>${text}</a>`;
	}
};

marked.use({ renderer });

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
		ADD_ATTR: ['class', 'target', 'rel']
	});
}

/**
 * Render plain text with auto-linked URLs and [[Wiki Links]].
 *
 * Unlike renderMarkdown, this does NOT parse markdown syntax — it only
 * linkifies bare URLs and wiki-link references, preserving the rest as
 * escaped plain text. Suitable for task descriptions and other non-markdown fields.
 *
 * @param text - Raw plain text
 * @param resolvedSlugs - Map of page title → slug (null = page doesn't exist)
 * @returns Sanitized HTML string
 */
export function renderRichText(
	text: string,
	resolvedSlugs: Record<string, string | null> = {}
): string {
	// Match wiki links and bare URLs on the RAW text (before HTML-escaping)
	// to avoid entity-related truncation and key-mismatch bugs.
	const pattern = /\[\[([^\]]+)\]\]|https?:\/\/[^\s<>"]+/g;
	const parts: string[] = [];
	let lastIndex = 0;
	let m: RegExpExecArray | null;

	while ((m = pattern.exec(text)) !== null) {
		// Escape the plain-text gap before this match
		if (m.index > lastIndex) {
			parts.push(escapeHtml(text.slice(lastIndex, m.index)));
		}

		const match = m[0];
		if (match.startsWith('[[') && match.endsWith(']]')) {
			// Wiki link — lookup uses the raw title (same key as extractWikiLinks)
			const title = match.slice(2, -2).trim();
			const escaped = escapeHtml(title);
			const slug = resolvedSlugs[title];
			if (slug) {
				parts.push(`<a href="/wiki/${encodeURIComponent(slug)}" class="wiki-link">${escaped}</a>`);
			} else {
				parts.push(
					`<a href="/wiki/new?title=${encodeURIComponent(title)}" class="wiki-link wiki-link-missing">${escaped}</a>`
				);
			}
		} else {
			// Bare URL — strip trailing punctuation that's likely not part of the URL
			let url = match;
			let trailing = '';
			const trailingMatch = url.match(/[.,;:!?)]+$/);
			if (trailingMatch) {
				trailing = trailingMatch[0];
				url = url.slice(0, -trailing.length);
			}
			parts.push(
				`<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(url)}</a>${escapeHtml(trailing)}`
			);
		}

		lastIndex = m.index + match.length;
	}

	// Escape any remaining text after the last match
	if (lastIndex < text.length) {
		parts.push(escapeHtml(text.slice(lastIndex)));
	}

	const html = parts.join('');
	return DOMPurify.sanitize(html, {
		ADD_ATTR: ['class', 'target', 'rel']
	});
}
