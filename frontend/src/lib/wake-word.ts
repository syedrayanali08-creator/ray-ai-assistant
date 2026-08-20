/**
 * Wake-word detection seam (ADR-0009).
 *
 * The eventual implementation is openWakeWord running on an audio worklet with a
 * trained "Ray" model. Phase 2 gets the same *shape* from the transcript that
 * browser speech recognition already produces, so switching detectors later does
 * not touch the conversation pipeline.
 *
 * `WakeEvent` carries which phrase fired because Ray is planned to answer to both
 * "Ray" and "Jarvis"; a detector that only reports "something fired" cannot
 * support that, and the caller may want to acknowledge by name.
 */

export interface WakeEvent {
  keyword: string;
  /** 0–1. Transcript matching is binary, so it reports 1. */
  confidence: number;
  at: number;
}

export interface WakeWordDetector {
  readonly keywords: readonly string[];
  /** Feed a (possibly interim) transcript. Returns an event when a keyword fires. */
  feed(transcript: string): WakeEvent | null;
  reset(): void;
}

export const DEFAULT_WAKE_WORDS = ["ray", "jarvis"] as const;

/**
 * Matches a keyword at a word boundary, and only reports it once until reset, so
 * a growing interim transcript does not fire on every update.
 */
export class TranscriptWakeWordDetector implements WakeWordDetector {
  private fired = false;

  constructor(readonly keywords: readonly string[] = DEFAULT_WAKE_WORDS) {}

  feed(transcript: string): WakeEvent | null {
    if (this.fired) return null;
    const text = transcript.toLowerCase();

    for (const keyword of this.keywords) {
      if (new RegExp(`\\b${keyword}\\b`).test(text)) {
        this.fired = true;
        return { keyword, confidence: 1, at: Date.now() };
      }
    }
    return null;
  }

  reset(): void {
    this.fired = false;
  }
}

/**
 * Strip the wake word from the front of an utterance.
 *
 * "Ray, what's on my calendar" is a question about the calendar, not about Ray.
 * A trailing comma or "please" style filler is dropped with it.
 */
export function stripWakeWord(transcript: string, keywords: readonly string[]): string {
  const pattern = new RegExp(`^\\s*(?:hey\\s+)?(?:${keywords.join("|")})\\b[,.:!?]?\\s*`, "i");
  return transcript.replace(pattern, "").trim();
}
