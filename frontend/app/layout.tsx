import type { Metadata } from "next";
import "./globals.css";
import QueryProvider from "@/providers/query-provider";

export const metadata: Metadata = {
  title: "Hive Trading System",
  description: "AI-Orchestrated Multi-Strategy Trading System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-gray-900 text-gray-100">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
