/**
 * Converts a human-readable name into a URL-safe slug.
 *
 * Rules:
 * - Lower-case everything
 * - Replace spaces and underscores with hyphens
 * - Strip any character that is not alphanumeric or a hyphen
 * - Collapse consecutive hyphens into one
 * - Trim leading/trailing hyphens
 *
 * @example
 * slugify('OSS UI Project')  // 'oss-ui-project'
 * slugify('Flow 1')          // 'flow-1'
 */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/[^a-z0-9-]/g, '')
    .replace(/-{2,}/g, '-')
    .replace(/^-+|-+$/g, '');
}
