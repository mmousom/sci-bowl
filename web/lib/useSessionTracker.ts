"use client";

import { useEffect, useRef } from "react";
import { useSession } from "next-auth/react";

const SESSION_TIMEOUT_MS = 5_000;

interface SessionTrackerActions {
  /** Start (or switch to) a session for the given topic. */
  startSession: (topic: string) => Promise<void>;
  /** End the current active session. */
  endSession: () => Promise<void>;
  /** Fire-and-forget increment of questionCount for the active session. */
  incrementQuestion: () => void;
}

/**
 * Manages the study session lifecycle on the client.
 * Tracks the active sessionId and topic via refs so state changes
 * don't cause re-renders. All API failures are swallowed silently.
 */
export function useSessionTracker(): SessionTrackerActions {
  const { data: authSession, status: authStatus } = useSession();
  const sessionIdRef = useRef<string | null>(null);
  const topicRef = useRef<string | null>(null);
  const pendingTopicRef = useRef<string | null>(null);

  /** End the active session with a 5-second timeout. */
  const endSession = async (): Promise<void> => {
    if (!sessionIdRef.current) return;
    const sessionId = sessionIdRef.current;
    const studentId = authSession?.user?.googleId;
    sessionIdRef.current = null;
    topicRef.current = null;

    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), SESSION_TIMEOUT_MS);
      await fetch("/api/sessions/end", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sessionId, studentId }),
        signal: controller.signal,
      });
      clearTimeout(timer);
    } catch {
      // Swallow — sign-out / topic-change proceeds regardless
    }
  };

  /** Start a session for the given topic, ending any existing one first. */
  const startSession = async (topic: string): Promise<void> => {
    if (!authSession?.user?.googleId) {
      // Auth not ready yet — store the topic and retry when auth loads
      pendingTopicRef.current = topic;
      return;
    }
    pendingTopicRef.current = null;
    if (topicRef.current === topic && sessionIdRef.current) return;

    // End previous session if topic changed
    if (sessionIdRef.current) {
      await endSession();
    }

    const studentId = authSession.user.googleId;
    try {
      const res = await fetch("/api/sessions/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ studentId, topic }),
      });
      if (res.ok) {
        const data = (await res.json()) as { sessionId: string };
        sessionIdRef.current = data.sessionId;
        topicRef.current = topic;
      }
    } catch {
      // Swallow — practice continues without tracking
    }
  };

  /** Increment questionCount for the active session (fire-and-forget). */
  const incrementQuestion = (): void => {
    if (!sessionIdRef.current) return;
    const sessionId = sessionIdRef.current;
    const studentId = authSession?.user?.googleId;

    fetch("/api/sessions/increment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sessionId, studentId }),
    }).catch(() => {
      // Swallow silently
    });
  };

  // When auth loads, start any session that was requested before auth was ready
  useEffect(() => {
    if (authStatus === "authenticated" && pendingTopicRef.current) {
      const topic = pendingTopicRef.current;
      pendingTopicRef.current = null;
      startSession(topic);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authStatus]);

  // Register beforeunload to end session when tab closes
  useEffect(() => {
    const handleUnload = () => {
      if (!sessionIdRef.current) return;
      const payload = JSON.stringify({
        sessionId: sessionIdRef.current,
        studentId: authSession?.user?.googleId,
      });
      const url = "/api/sessions/end";

      if (typeof navigator.sendBeacon === "function") {
        navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
      } else {
        fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        }).catch(() => {});
      }
    };

    window.addEventListener("beforeunload", handleUnload);
    return () => window.removeEventListener("beforeunload", handleUnload);
  }, [authSession?.user?.googleId]);

  return { startSession, endSession, incrementQuestion };
}
