"use client";

interface LiveTranscriptProps {
  text: string;
  interimText: string;
  isListening: boolean;
  isProcessing: boolean;
  supported: boolean;
}

export function LiveTranscript({
  text,
  interimText,
  isListening,
  isProcessing,
  supported,
}: LiveTranscriptProps) {
  const showPanel = isListening || isProcessing || Boolean(text || interimText);
  if (!showPanel) return null;

  const displayFinal = text.trim();
  const displayInterim = interimText.trim();
  const hasContent = displayFinal || displayInterim;

  return (
    <section
      className="w-full rounded-2xl border border-accent/30 bg-accent/5 p-4 min-h-[88px] transition-all"
      aria-live="polite"
      aria-label="Live transcription"
    >
      <div className="flex items-center gap-2 mb-2">
        <span
          className={`w-2 h-2 rounded-full ${
            isListening ? "bg-emerald-400 animate-pulse" : "bg-amber-400 animate-pulse"
          }`}
        />
        <span className="text-xs font-semibold uppercase tracking-wider text-accent-glow">
          {isListening ? "Live transcription" : "Processing speech"}
        </span>
      </div>

      {hasContent ? (
        <p className="text-base leading-relaxed text-white">
          {displayFinal && <span>{displayFinal}</span>}
          {displayInterim && (
            <span className="text-gray-400 italic">{displayInterim}</span>
          )}
        </p>
      ) : (
        <p className="text-sm text-gray-500 italic">
          {isListening ? "Start speaking…" : "Sending to assistant…"}
        </p>
      )}

      {isListening && !supported && (
        <p className="text-xs text-amber-400/90 mt-2">
          Live captions need Chrome or Edge. Your speech is still recorded.
        </p>
      )}
    </section>
  );
}
