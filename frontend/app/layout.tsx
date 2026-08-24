import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ChessTempo",
  description: "A chess mentor that grows with you instead of playing at a fixed ELO.",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
