import "./globals.css";
import "@xyflow/react/dist/style.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Yohan",
  description: "Personal agent control plane — live traces",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
