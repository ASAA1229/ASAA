export function assertHttps(url, label) {
  const parsed = new URL(url);
  if (parsed.protocol !== "https:" && !["localhost", "127.0.0.1"].includes(parsed.hostname)) {
    throw new Error(label + " must use HTTPS.");
  }
  return parsed;
}
