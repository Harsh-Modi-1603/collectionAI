/**
 * parseTicketIds — splits a raw input string into a clean array of JIRA ticket IDs.
 * Accepts comma-separated, newline-separated, or mixed input.
 * Trims whitespace, filters empty strings, and deduplicates.
 */
export function parseTicketIds(input) {
  if (!input || typeof input !== "string") return [];
  const seen = new Set();
  return input
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
    .filter((s) => {
      if (seen.has(s)) return false;
      seen.add(s);
      return true;
    });
}

/**
 * deriveFilename — returns the download filename for a generated collection.
 * Uses collectionName if provided, otherwise falls back to the first ticket ID.
 */
export function deriveFilename(collectionName, ticketIds) {
  const base = collectionName || (ticketIds && ticketIds[0]) || "collection";
  return `${base}_collection.json`;
}
