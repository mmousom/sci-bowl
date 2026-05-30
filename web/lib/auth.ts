import type { NextAuthOptions } from "next-auth";
import GoogleProvider from "next-auth/providers/google";

export const AUTH_OPTIONS: NextAuthOptions = {
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    jwt({ token, account, profile }) {
      if (account?.provider === "google" && profile?.sub) {
        token.googleId = profile.sub;
      }
      return token;
    },
    session({ session, token }) {
      if (token.googleId) {
        session.user.googleId = token.googleId as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
    error: "/login",
  },
};
