/** Filter phantom / echo phrases from browser speech recognition. */

const GARBAGE_PHRASES = new Set([
  "thank you",
  "thanks",
  "thank you so much",
  "you",
  "uh",
  "um",
  "hmm",
  "the",
  "a",
  "ok",
  "okay",
  "bye",
  "hello",
  "hey",
]);

const SHORT_VALID = new Set(["yes", "no", "yeah", "yep", "nope", "sure", "cancel", "stop"]);

export function isMeaningfulTranscript(text: string): boolean {
  const normalized = text.trim().toLowerCase().replace(/[^\w\s']/g, "").trim();
  if (!normalized) return false;
  if (SHORT_VALID.has(normalized)) return true;
  if (GARBAGE_PHRASES.has(normalized)) return false;
  if (normalized.length < 4 && !normalized.includes(" ")) return false;
  return true;
}
