"use client";

import { SessionProvider } from "next-auth/react";
import type { ReactNode } from "react";

interface SessionProviderWrapperProps {
  children: ReactNode;
}

/**
 * Client-side wrapper that provides the NextAuth session context
 * to all child components via useSession().
 */
export default function SessionProviderWrapper({
  children,
}: SessionProviderWrapperProps) {
  return <SessionProvider>{children}</SessionProvider>;
}
