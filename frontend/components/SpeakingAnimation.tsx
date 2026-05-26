"use client";

import type { AssistantStatus } from "@/lib/types";

interface SpeakingAnimationProps {
  status: AssistantStatus;
}

export function SpeakingAnimation({ status }: SpeakingAnimationProps) {
  const isActive = status === "speaking" || status === "listening" || status === "processing";

  return (
    <div className="relative flex items-center justify-center w-32 h-32">
      {status === "speaking" && (
        <>
          <span className="absolute inset-0 rounded-full bg-accent/20 animate-pulse-ring" />
          <span className="absolute inset-2 rounded-full bg-accent/15 animate-pulse-ring animation-delay-150" />
        </>
      )}
      <div
        className={`relative z-10 flex items-center justify-center w-24 h-24 rounded-full border-2 transition-all duration-300 ${
          status === "speaking"
            ? "border-accent bg-accent/20 shadow-lg shadow-accent/30"
            : status === "listening"
              ? "border-emerald-500/60 bg-emerald-500/10"
              : status === "processing"
                ? "border-amber-500/60 bg-amber-500/10"
                : "border-surface-border bg-surface-elevated"
        }`}
      >
        {isActive ? (
          <div className="flex items-end justify-center gap-1 h-8">
            {[0, 1, 2, 3, 4].map((i) => (
              <div
                key={i}
                className="w-1 bg-accent-glow rounded-full animate-wave"
                style={{ animationDelay: `${i * 0.12}s` }}
              />
            ))}
          </div>
        ) : (
          <div className="w-3 h-3 rounded-full bg-surface-border" />
        )}
      </div>
    </div>
  );
}
