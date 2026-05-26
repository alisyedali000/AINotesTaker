"use client";

interface MicrophoneButtonProps {
  isListening: boolean;
  disabled?: boolean;
  onClick: () => void;
}

export function MicrophoneButton({ isListening, disabled, onClick }: MicrophoneButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className={`relative flex items-center justify-center w-20 h-20 rounded-full transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface disabled:opacity-40 disabled:cursor-not-allowed ${
        isListening
          ? "bg-red-500 hover:bg-red-600 shadow-lg shadow-red-500/40 scale-105"
          : "bg-accent hover:bg-accent-glow shadow-lg shadow-accent/30"
      }`}
      aria-label={isListening ? "Stop listening" : "Start listening"}
      aria-pressed={isListening}
    >
      {isListening && (
        <span className="absolute inset-0 rounded-full bg-red-500/40 animate-ping" />
      )}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24"
        fill="currentColor"
        className="w-9 h-9 text-white relative z-10"
      >
        <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
        <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
      </svg>
    </button>
  );
}
