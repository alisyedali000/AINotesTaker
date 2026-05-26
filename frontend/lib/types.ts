export type ConnectionStatus = "disconnected" | "connecting" | "connected" | "error";

export type AssistantStatus = "idle" | "listening" | "processing" | "speaking";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

export interface WsServerMessage {
  type: string;
  status?: string;
  role?: string;
  text?: string;
  data?: string;
  format?: string;
  message?: string;
  session_id?: string;
}
