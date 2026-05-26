"use client";

import type { ConnectionStatus as ConnStatus } from "@/lib/types";

const labels: Record<ConnStatus, string> = {
  disconnected: "Disconnected",
  connecting: "Connecting...",
  connected: "Connected",
  error: "Connection error",
};

const colors: Record<ConnStatus, string> = {
  disconnected: "bg-gray-500",
  connecting: "bg-amber-500 animate-pulse",
  connected: "bg-emerald-500",
  error: "bg-red-500",
};

export function ConnectionStatusBadge({ status }: { status: ConnStatus }) {
  return (
    <div className="flex items-center gap-2 text-sm text-gray-400">
      <span className={`w-2 h-2 rounded-full ${colors[status]}`} />
      <span>{labels[status]}</span>
    </div>
  );
}
