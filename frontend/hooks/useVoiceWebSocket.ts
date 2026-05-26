"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  type BrowserSpeechRecognition,
  getSpeechRecognition,
  isSpeechRecognitionSupported,
} from "@/lib/speechRecognition";
import { isMeaningfulTranscript } from "@/lib/transcriptFilter";
import type { AssistantStatus, ConnectionStatus, Message, WsServerMessage } from "@/lib/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws/voice";
const SILENCE_MS = 1400;
const SPEECH_THRESHOLD = 18;
const INTERRUPT_THRESHOLD = 50;

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const result = reader.result as string;
      resolve(result.split(",")[1] || "");
    };
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export function useVoiceWebSocket() {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>("disconnected");
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus>("idle");
  const [messages, setMessages] = useState<Message[]>([]);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const [isProcessingSpeech, setIsProcessingSpeech] = useState(false);
  const [speechSupported] = useState(() => isSpeechRecognitionSupported());
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const ttsChunksRef = useRef<Uint8Array[]>([]);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  const isSpeakingRef = useRef(false);
  const recordMimeRef = useRef("audio/webm");
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const vadIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const speechRecognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const accumulatedFinalRef = useRef("");
  const isListeningRef = useRef(false);
  const isProcessingRef = useRef(false);
  const hasHeardSpeechRef = useRef(false);
  const lastSpeechAtRef = useRef(0);
  const isFinalizingRef = useRef(false);

  const addMessage = useCallback((role: "user" | "assistant", text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: generateId(), role, text, timestamp: new Date() },
    ]);
  }, []);

  const stopPlayback = useCallback(() => {
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current.src = "";
      ttsAudioRef.current = null;
    }
    ttsChunksRef.current = [];
    isSpeakingRef.current = false;
  }, []);

  const playTtsAudio = useCallback(async () => {
    if (ttsChunksRef.current.length === 0) return;
    const blob = new Blob(ttsChunksRef.current as BlobPart[], { type: "audio/mpeg" });
    ttsChunksRef.current = [];
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    ttsAudioRef.current = audio;
    try {
      await audio.play();
    } catch (e) {
      console.warn("TTS playback failed:", e);
      URL.revokeObjectURL(url);
      return;
    }
    audio.onended = () => {
      URL.revokeObjectURL(url);
      if (ttsAudioRef.current === audio) ttsAudioRef.current = null;
      isSpeakingRef.current = false;
      setAssistantStatus("listening");
    };
  }, []);

  const stopSpeechRecognition = useCallback(() => {
    const recognition = speechRecognitionRef.current;
    if (recognition) {
      try {
        recognition.stop();
      } catch {
        /* already stopped */
      }
      speechRecognitionRef.current = null;
    }
  }, []);

  const sendInterrupt = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "interrupt" }));
    }
    stopPlayback();
  }, [stopPlayback]);

  const handleServerMessage = useCallback(
    async (data: WsServerMessage) => {
      switch (data.type) {
        case "connected":
          setConnectionStatus("connected");
          setError(null);
          break;
        case "status":
          if (data.status === "listening") {
            setAssistantStatus("listening");
            isProcessingRef.current = false;
          } else if (data.status === "processing") {
            setAssistantStatus("processing");
            isProcessingRef.current = true;
            stopSpeechRecognition();
          } else if (data.status === "speaking") {
            setAssistantStatus("speaking");
            isSpeakingRef.current = true;
            stopSpeechRecognition();
          }
          break;
        case "transcript":
          if (data.role && data.text) {
            addMessage(data.role as "user" | "assistant", data.text);
            if (data.role === "user") {
              setLiveTranscript("");
              setInterimTranscript("");
              setIsProcessingSpeech(false);
              accumulatedFinalRef.current = "";
            }
          }
          break;
        case "tts_start":
          ttsChunksRef.current = [];
          setAssistantStatus("speaking");
          isSpeakingRef.current = true;
          break;
        case "audio_chunk":
          if (data.data && data.format === "mp3") {
            const binary = atob(data.data);
            const bytes = new Uint8Array(binary.length);
            for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
            ttsChunksRef.current.push(bytes);
          }
          break;
        case "tts_end":
          await playTtsAudio();
          if (!ttsAudioRef.current) {
            isSpeakingRef.current = false;
            setAssistantStatus("listening");
          }
          break;
        case "tts_cancelled":
          stopPlayback();
          isSpeakingRef.current = false;
          setAssistantStatus("listening");
          break;
        case "error":
          setError(data.message || "Something went wrong");
          break;
        case "pong":
          break;
        default:
          break;
      }
    },
    [addMessage, playTtsAudio, stopPlayback, stopSpeechRecognition]
  );

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setConnectionStatus("connecting");
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnectionStatus("connected");
      setAssistantStatus("listening");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as WsServerMessage;
        void handleServerMessage(data);
      } catch {
        setError("Invalid server response");
      }
    };

    ws.onerror = () => {
      setConnectionStatus("error");
      setError("WebSocket connection failed");
    };

    ws.onclose = () => {
      setConnectionStatus("disconnected");
      setAssistantStatus("idle");
      reconnectTimeoutRef.current = setTimeout(() => connect(), 3000);
    };
  }, [handleServerMessage]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    wsRef.current?.close();
    wsRef.current = null;
    setConnectionStatus("disconnected");
  }, []);

  const startSpeechRecognition = useCallback(() => {
    const SpeechRecognitionCtor = getSpeechRecognition();
    if (!SpeechRecognitionCtor) return;

    accumulatedFinalRef.current = "";
    setLiveTranscript("");
    setInterimTranscript("");

    const recognition = new SpeechRecognitionCtor();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = accumulatedFinalRef.current;

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          final += transcript;
        } else {
          interim += transcript;
        }
      }

      accumulatedFinalRef.current = final;
      setLiveTranscript(final);
      setInterimTranscript(interim);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error !== "aborted" && event.error !== "no-speech") {
        console.warn("Speech recognition:", event.error);
      }
    };

    recognition.onend = () => {
      if (
        speechRecognitionRef.current === recognition &&
        isListeningRef.current &&
        !isSpeakingRef.current &&
        !isProcessingRef.current
      ) {
        try {
          recognition.start();
        } catch {
          /* restart throttled */
        }
      }
    };

    try {
      recognition.start();
      speechRecognitionRef.current = recognition;
    } catch {
      console.warn("Could not start speech recognition");
    }
  }, []);

  const finalizeListening = useCallback(async () => {
    if (isFinalizingRef.current || !isListeningRef.current) return;
    isFinalizingRef.current = true;
    isListeningRef.current = false;
    setIsListening(false);

    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.requestData();
      mediaRecorderRef.current.stop();
    } else {
      stopSpeechRecognition();
      setIsProcessingSpeech(true);
      setAssistantStatus("processing");
    }
    isFinalizingRef.current = false;
  }, [stopSpeechRecognition]);

  // Monitor mic: auto-send after silence; interrupt assistant only on clear speech
  const monitorAudio = useCallback(() => {
    if (!analyserRef.current) return;
    const data = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(data);
    const avg = data.reduce((a, b) => a + b, 0) / data.length;

    if (isSpeakingRef.current) {
      if (avg > INTERRUPT_THRESHOLD) sendInterrupt();
      return;
    }

    if (!isListeningRef.current || isProcessingRef.current) return;

    if (avg > SPEECH_THRESHOLD) {
      lastSpeechAtRef.current = Date.now();
      hasHeardSpeechRef.current = true;
    } else if (
      hasHeardSpeechRef.current &&
      Date.now() - lastSpeechAtRef.current > SILENCE_MS
    ) {
      hasHeardSpeechRef.current = false;
      void finalizeListening();
    }
  }, [sendInterrupt, finalizeListening]);

  const startContinuousListening = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      await new Promise((r) => setTimeout(r, 500));
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;
      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      hasHeardSpeechRef.current = false;
      lastSpeechAtRef.current = Date.now();
      isListeningRef.current = true;
      vadIntervalRef.current = setInterval(monitorAudio, 100);

      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/mp4")
          ? "audio/mp4"
          : "audio/webm";
      recordMimeRef.current = mimeType;

      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };

      recorder.onstop = async () => {
        stopSpeechRecognition();
        const ws = wsRef.current;
        if (ws?.readyState === WebSocket.OPEN) {
          const blob = new Blob(audioChunksRef.current, { type: mimeType });
          audioChunksRef.current = [];

          const hint = accumulatedFinalRef.current.trim();
          if (hint && isMeaningfulTranscript(hint)) {
            ws.send(JSON.stringify({ type: "text_hint", text: hint }));
          }

          if (blob.size > 0) {
            try {
              const base64 = await blobToBase64(blob);
              ws.send(
                JSON.stringify({ type: "audio_upload", data: base64, mime: mimeType })
              );
            } catch {
              setError("Could not process recording");
            }
          }

          ws.send(JSON.stringify({ type: "audio_end" }));
        }
        setAssistantStatus("processing");
        setIsProcessingSpeech(true);
      };

      recorder.start(250);
      startSpeechRecognition();
      setIsListening(true);
      setAssistantStatus("listening");
      setIsProcessingSpeech(false);
      isProcessingRef.current = false;
    } catch {
      setError("Microphone access denied. Please allow microphone permissions.");
    }
  }, [connect, monitorAudio, startSpeechRecognition, stopSpeechRecognition]);

  const stopListeningAndSend = useCallback(() => {
    void finalizeListening();
  }, [finalizeListening]);

  const toggleListening = useCallback(() => {
    if (isListeningRef.current) {
      void finalizeListening();
      return;
    }
    if (isProcessingRef.current) return;
    if (isSpeakingRef.current) sendInterrupt();
    void startContinuousListening();
  }, [finalizeListening, sendInterrupt, startContinuousListening]);

  const stopAll = useCallback(() => {
    stopSpeechRecognition();
    if (vadIntervalRef.current) {
      clearInterval(vadIntervalRef.current);
      vadIntervalRef.current = null;
    }
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    mediaRecorderRef.current = null;
    isListeningRef.current = false;
    isProcessingRef.current = false;
    hasHeardSpeechRef.current = false;
    setIsListening(false);
    setIsProcessingSpeech(false);
    setLiveTranscript("");
    setInterimTranscript("");
    stopPlayback();
  }, [stopPlayback, stopSpeechRecognition]);

  useEffect(() => {
    connect();
    return () => {
      stopAll();
      disconnect();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Keep-alive ping
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "ping" }));
      }
    }, 25000);
    return () => clearInterval(interval);
  }, []);

  return {
    connectionStatus,
    assistantStatus,
    messages,
    liveTranscript,
    interimTranscript,
    isProcessingSpeech,
    speechSupported,
    isListening,
    error,
    connect,
    disconnect,
    startContinuousListening,
    stopListeningAndSend,
    stopAll,
    sendInterrupt,
    toggleListening,
  };
}
