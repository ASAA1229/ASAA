// Loopback only: URL.hostname keeps the brackets of an IPv6 literal ("[::1]"). Lookalikes such as 127.0.0.1.evil.example never match.
const LOOPBACK_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function assertHttps(url, label) {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" && !LOOPBACK_HOSTS.has(parsed.hostname)) {
    throw new Error(label + " must use HTTPS.");
  }
  return parsed;
}
