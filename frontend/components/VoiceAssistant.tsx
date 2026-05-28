"use client";

import { useVoiceWebSocket } from "@/hooks/useVoiceWebSocket";
import { ConnectionStatusBadge } from "./ConnectionStatus";
import { ConversationHistory } from "./ConversationHistory";
import { LiveTranscript } from "./LiveTranscript";
import { MicrophoneButton } from "./MicrophoneButton";
import { SpeakingAnimation } from "./SpeakingAnimation";

const statusLabels = {
  idle: "Ready",
  listening: "Listening",
  processing: "Thinking...",
  speaking: "Speaking",
};

export function VoiceAssistant() {
  const {
    connectionStatus,
    assistantStatus,
    messages,
    liveTranscript,
    interimTranscript,
    isProcessingSpeech,
    speechSupported,
    isListening,
    error,
    toggleListening,
  } = useVoiceWebSocket();

  const handleMicClick = () => {
    toggleListening();
  };

  return (
    <div className="flex flex-col h-[100dvh] max-h-[100dvh] max-w-lg mx-auto px-4 py-6 overflow-hidden">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">
            Voice Task Manager
          </h1>
          <p className="text-xs text-gray-500 mt-0.5">Speak naturally — no typing needed</p>
        </div>
        <ConnectionStatusBadge status={connectionStatus} />
      </header>

      <main className="flex-1 flex flex-col gap-4 min-h-0 overflow-hidden">
        <div className="flex flex-col items-center gap-2 py-2 shrink-0">
          <SpeakingAnimation status={assistantStatus} />
          <p className="text-sm font-medium text-gray-400">
            {statusLabels[assistantStatus]}
          </p>
        </div>

        <LiveTranscript
          text={liveTranscript}
          interimText={interimTranscript}
          isListening={isListening}
          isProcessing={isProcessingSpeech}
          supported={speechSupported}
        />

        <div className="flex flex-col flex-1 min-h-0 rounded-2xl border border-surface-border bg-surface-elevated/50 p-3 backdrop-blur-sm overflow-hidden">
          <ConversationHistory messages={messages} />
        </div>

        {error && (
          <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-2 text-center">
            {error}
          </div>
        )}
      </main>

      <footer className="flex flex-col items-center gap-3 pt-4 pb-2 shrink-0">
        <MicrophoneButton
          isListening={isListening}
          disabled={connectionStatus !== "connected" || assistantStatus === "processing"}
          onClick={handleMicClick}
        />
        <p className="text-xs text-gray-500 text-center">
          Tap to speak · Stops automatically after you pause · Tap again to send early
        </p>
      </footer>
    </div>
  );
}
