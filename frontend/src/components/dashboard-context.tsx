"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { components } from "@/lib/api-types";
import type { Health, User } from "@/lib/api";
import type { VoiceState } from "@/hooks/use-voice";

type Invocation = components["schemas"]["ToolInvocationRead"];

interface DashboardContextValue {
  health: Health | null;
  user: User | null;
  voiceState: VoiceState;
  agentName: string | undefined;
  pendingApprovals: number;
  approvals: Invocation[];
  setVoiceState: (state: VoiceState) => void;
  setAgentName: (name: string | undefined) => void;
  refreshApprovals: () => Promise<void>;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function useDashboard() {
  const value = useContext(DashboardContext);
  if (value === null) throw new Error("useDashboard must be used within DashboardProvider");
  return value;
}

interface DashboardProviderProps {
  health: Health | null;
  user: User | null;
  children: ReactNode;
}

export function DashboardProvider({ health, user, children }: DashboardProviderProps) {
  const [voiceState, setVoiceState] = useState<VoiceState>("idle");
  const [agentName, setAgentName] = useState<string | undefined>(undefined);
  const [approvals, setApprovals] = useState<Invocation[]>([]);

  const refreshApprovals = useCallback(async () => {
    try {
      const response = await fetch("/api/approvals", { cache: "no-store" });
      if (!response.ok) return;
      const data = (await response.json()) as Invocation[];
      setApprovals(data);
    } catch {
      // Backend may still be starting; the next interval will retry.
    }
  }, []);

  useEffect(() => {
    void refreshApprovals();
    const interval = setInterval(() => void refreshApprovals(), 3000);
    return () => clearInterval(interval);
  }, [refreshApprovals]);

  const value = useMemo(
    () => ({
      health,
      user,
      voiceState,
      agentName,
      pendingApprovals: approvals.length,
      approvals,
      setVoiceState,
      setAgentName,
      refreshApprovals,
    }),
    [health, user, voiceState, agentName, approvals, refreshApprovals],
  );

  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}
