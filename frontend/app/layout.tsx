import type { Metadata } from "next";
import { Inter, IBM_Plex_Mono } from "next/font/google";
import Script from "next/script";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "900"],
  variable: "--font-sans",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Soft-Cases — Citation Intelligence",
  description:
    "Discover and score authoritative sources for Claim Sets. Powered by Perplexity, Semantic Scholar, and arXiv.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const shellUrl =
    process.env.NEXT_PUBLIC_SHELL_DASHBOARD_URL?.replace("/dashboard", "") ||
    "https://shell-production-3509.up.railway.app";

  return (
    <html lang="en" className={`${inter.variable} ${ibmPlexMono.variable}`}>
      <body className="bg-background text-foreground font-sans antialiased min-h-screen">
        <Script
          src={`${shellUrl}/nav-bar.v1.js`}
          data-service="soft-cases"
          data-shell-url={shellUrl}
          strategy="afterInteractive"
        />
        <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {children}
        </main>
      </body>
    </html>
  );
}
