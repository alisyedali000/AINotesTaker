"use client";

import type { Message } from "@/lib/types";

interface ConversationHistoryProps {
  messages: Message[];
}

export function ConversationHistory({ messages }: ConversationHistoryProps) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6 text-gray-500">
        <p className="text-lg font-medium text-gray-400 mb-2">Start talking</p>
        <p className="text-sm max-w-sm">
          Tap the microphone and say something like &quot;Create a task for gym tomorrow at 7
          AM&quot; or &quot;What&apos;s on my agenda today?&quot;
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 overflow-y-auto h-full pr-2 scroll-smooth">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-accent/20 text-indigo-100 rounded-br-md"
                : "bg-surface-elevated border border-surface-border text-gray-200 rounded-bl-md"
            }`}
          >
            <span className="text-xs font-medium opacity-60 block mb-1 capitalize">
              {msg.role === "user" ? "You" : "Assistant"}
            </span>
            {msg.text}
          </div>
        </div>
      ))}
    </div>
  );
}
