import type { Metadata } from "next";
import { Inter } from "next/font/google";
import Nav from "@/components/Nav";
import SessionProviderWrapper from "@/components/SessionProviderWrapper";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "BowlPrep",
  description: "Practice Science Bowl questions",
};

/**
 * Root layout for the BowlPrep app.
 * Applies the Inter font, surface background, and responsive horizontal padding.
 * Renders the Nav component above all page content.
 */
export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-surface dark:bg-[#0f0f14]`}>
        <SessionProviderWrapper>
          <Nav />
          <main className="px-4 md:px-10">
            {children}
          </main>
        </SessionProviderWrapper>
      </body>
    </html>
  );
}
