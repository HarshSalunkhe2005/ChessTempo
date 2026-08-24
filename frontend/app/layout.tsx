import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ChessTempo",
  description: "A chess mentor that grows with you instead of playing at a fixed ELO.",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#111318", color: "#eee" }}>
        {children}
      </body>
    </html>
  );
}
