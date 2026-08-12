"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  DEFAULT_WAKE_WORDS,
  TranscriptWakeWordDetector,
  stripWakeWord,
  type WakeEvent,
} from "@/lib/wake-word";

/**
 * The browser end of the voice round trip (ADR-0009).
 *
 * Two independent browser APIs, deliberately kept behind one state machine whose
 * states are the pipeline's real states, so the local faster-whisper/Piper/
 * openWakeWord backends can replace them without the UI changing:
 *
 *   idle → armed → listening → thinking → speaking → armed
 *
 * Note that `RAY_STT_BACKEND=browser` is not local: Chrome sends the captured
 * audio to Google for transcription (docs/12). That is why the control shows
 * which backend is active instead of just a microphone icon.
 */

export type VoiceState = "idle" | "armed" | "listening" | "thinking" | "speaking";

/** Minimal shape of the Web Speech API, which TypeScript's DOM lib omits. */
interface SpeechRecognitionAlternative {
  transcript: string;
}
interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly length: number;
  [index: number]: SpeechRecognitionAlternative;
}
interface SpeechRecognitionEventLike {
  readonly resultIndex: number;
  readonly results: {
    readonly length: number;
    [index: number]: SpeechRecognitionResult;
  };
}
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function recognitionConstructor(): SpeechRecognitionConstructor | null {
  if (typeof window === "undefined") return null;
  const candidate = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return candidate.SpeechRecognition ?? candidate.webkitSpeechRecognition ?? null;
}

export interface UseVoiceOptions {
  /** Called with the user's request, wake word already stripped. */
  onRequest: (text: string) => void;
  wakeWords?: readonly string[];
  wakeWordEnabled?: boolean;
}

export interface Voice {
  state: VoiceState;
  supported: boolean;
  /** Interim transcript, so the user can see they are being heard. */
  transcript: string;
  lastWake: WakeEvent | null;
  error: string | null;
  speechEnabled: boolean;
  toggleSpeech: () => void;
  /** Arm wake-word listening, or disarm it. */
  toggleArmed: () => void;
  /** Listen for one utterance, no wake word needed. */
  pushToTalk: () => void;
  stop: () => void;
  setThinking: (thinking: boolean) => void;
  speak: (text: string) => void;
}

export function useVoice({
  onRequest,
  wakeWords = DEFAULT_WAKE_WORDS,
  wakeWordEnabled = false,
}: UseVoiceOptions): Voice {
  const [state, setState] = useState<VoiceState>("idle");
  const [transcript, setTranscript] = useState("");
  const [lastWake, setLastWake] = useState<WakeEvent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [speechEnabled, setSpeechEnabled] = useState(false);

  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const detector = useMemo(() => new TranscriptWakeWordDetector(wakeWords), [wakeWords]);
  // Wake mode keeps the microphone open and waits for the keyword; push-to-talk
  // takes the whole utterance and then stops.
  const modeRef = useRef<"wake" | "push">("wake");
  const armedRef = useRef(false);
  const requestRef = useRef(onRequest);
  requestRef.current = onRequest;

  // Capability is browser-only, so it cannot be read during render: the server
  // renders "unsupported" and the client would disagree, which is a hydration
  // mismatch. It resolves in an effect, after hydration.
  const [supported, setSupported] = useState(false);
  const [speechSupported, setSpeechSupported] = useState(false);
  useEffect(() => {
    setSupported(recognitionConstructor() !== null);
    setSpeechSupported(typeof window.speechSynthesis !== "undefined");
  }, []);

  const stop = useCallback(() => {
    armedRef.current = false;
    recognitionRef.current?.abort();
    recognitionRef.current = null;
    detector.reset();
    setTranscript("");
    setState("idle");
  }, [detector]);

  const start = useCallback(
    (mode: "wake" | "push") => {
      const Recognition = recognitionConstructor();
      if (Recognition === null) {
        setError("This browser has no speech recognition. Type instead.");
        return;
      }

      recognitionRef.current?.abort();
      detector.reset();
      modeRef.current = mode;
      armedRef.current = true;
      setError(null);
      setTranscript("");

      const recognition = new Recognition();
      recognition.continuous = mode === "wake";
      recognition.interimResults = true;
      recognition.lang = "en-US";

      recognition.onresult = (event) => {
        let interim = "";
        let final = "";
        for (let index = event.resultIndex; index < event.results.length; index += 1) {
          const result = event.results[index];
          if (result.isFinal) final += result[0].transcript;
          else interim += result[0].transcript;
        }
        const heard = `${final}${interim}`;
        setTranscript(heard);

        if (modeRef.current === "wake") {
          const wake = detector.feed(heard);
          if (wake !== null) {
            setLastWake(wake);
            setState("listening");
          }
        }

        if (final.trim() === "") return;

        const spoken =
          modeRef.current === "wake" ? stripWakeWord(final, detector.keywords) : final.trim();

        // In wake mode the keyword alone is an activation, not a request: keep
        // listening for what the user actually wants.
        if (spoken === "") {
          detector.reset();
          return;
        }

        setTranscript("");
        detector.reset();
        setState("thinking");
        if (modeRef.current === "push") {
          recognition.stop();
        }
        requestRef.current(spoken);
      };

      recognition.onerror = (event) => {
        if (event.error === "no-speech" || event.error === "aborted") return;
        setError(
          event.error === "not-allowed"
            ? "Microphone permission denied. Allow it in the browser to talk to Ray."
            : `Speech recognition failed (${event.error}).`,
        );
        armedRef.current = false;
        setState("idle");
      };

      recognition.onend = () => {
        // Chrome ends the session after a pause; wake mode must stay armed.
        if (armedRef.current && modeRef.current === "wake") {
          try {
            recognition.start();
            return;
          } catch {
            // Restarting too quickly throws; fall through and disarm.
          }
        }
        armedRef.current = false;
        setState((current) => (current === "thinking" ? current : "idle"));
      };

      recognitionRef.current = recognition;
      try {
        recognition.start();
        setState(mode === "wake" ? "armed" : "listening");
      } catch {
        setError("Could not start the microphone.");
        setState("idle");
      }
    },
    [detector],
  );

  const toggleArmed = useCallback(() => {
    if (state === "idle") start("wake");
    else stop();
  }, [state, start, stop]);

  const pushToTalk = useCallback(() => {
    if (state === "listening") stop();
    else start("push");
  }, [state, start, stop]);

  const setThinking = useCallback((thinking: boolean) => {
    setState((current) => {
      if (thinking) return "thinking";
      if (current === "thinking") return armedRef.current ? "armed" : "idle";
      return current;
    });
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (!speechEnabled || !speechSupported || text.trim() === "") return;

      window.speechSynthesis.cancel();
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 1.05;
      utterance.onstart = () => setState("speaking");
      utterance.onend = () => setState(armedRef.current ? "armed" : "idle");
      window.speechSynthesis.speak(utterance);
    },
    [speechEnabled, speechSupported],
  );

  const toggleSpeech = useCallback(() => {
    setSpeechEnabled((enabled) => {
      if (enabled) window.speechSynthesis.cancel();
      return !enabled;
    });
  }, []);

  // Arming needs a user gesture for microphone permission, so a backend that
  // reports wake word enabled cannot auto-arm; it only makes the affordance the
  // primary one.
  useEffect(() => {
    if (!wakeWordEnabled) return;
    setError(null);
  }, [wakeWordEnabled]);

  useEffect(() => stop, [stop]);

  return {
    state,
    supported,
    transcript,
    lastWake,
    error,
    speechEnabled: speechEnabled && speechSupported,
    toggleSpeech,
    toggleArmed,
    pushToTalk,
    stop,
    setThinking,
    speak,
  };
}
