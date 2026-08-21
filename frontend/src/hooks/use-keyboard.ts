"use client";

import { useEffect } from "react";

interface UseKeyboardShortcutsOptions {
  onFocus: () => void;
  onStop: () => void;
  onToggleArmed?: () => void;
}

function isTypingTarget(event: KeyboardEvent): boolean {
  const target = event.target as HTMLElement | null;
  if (target === null) return false;
  return (
    target.tagName === "INPUT" ||
    target.tagName === "TEXTAREA" ||
    target.isContentEditable
  );
}

/**
 * Global keyboard shortcuts for the dashboard.
 *
 * - `/` or `Cmd/Ctrl+K` focuses the composer
 * - `Escape` stops the current voice/speech action
 * - `Cmd/Ctrl+Shift+L` toggles wake-word arming
 */
export function useKeyboardShortcuts({
  onFocus,
  onStop,
  onToggleArmed,
}: UseKeyboardShortcutsOptions) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const mod = event.metaKey || event.ctrlKey;

      if (event.key === "Escape") {
        event.preventDefault();
        onStop();
        return;
      }

      if ((event.key === "/" && !isTypingTarget(event)) || ((event.key === "k" || event.key === "K") && mod)) {
        event.preventDefault();
        onFocus();
        return;
      }

      if (event.key === "L" && mod && event.shiftKey && onToggleArmed) {
        event.preventDefault();
        onToggleArmed();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onFocus, onStop, onToggleArmed]);
}
