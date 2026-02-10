/**
 * Convert a hex color to a lighter 50% shade for backgrounds
 * @param hex - Hex color string (e.g., "#3b82f6" or "3b82f6")
 * @returns Lighter shade as hex color
 */
export function hexTo50Shade(hex: string): string {
	// Remove # if present
	hex = hex.replace(/^#/, '');

	// Parse RGB values
	const r = parseInt(hex.substring(0, 2), 16);
	const g = parseInt(hex.substring(2, 4), 16);
	const b = parseInt(hex.substring(4, 6), 16);

	// Lighten by mixing with white (50% lighter)
	const lighten = (value: number) => Math.round(value + (255 - value) * 0.85);

	const newR = lighten(r);
	const newG = lighten(g);
	const newB = lighten(b);

	// Convert back to hex
	const toHex = (value: number) => value.toString(16).padStart(2, '0');

	return `#${toHex(newR)}${toHex(newG)}${toHex(newB)}`;
}
