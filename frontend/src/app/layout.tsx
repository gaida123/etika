import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "etika",
  description: "Compliance navigator for new Vancouver, BC businesses",
  // favicon.ico (16 and 32) is picked up from src/app automatically; the rest live in public/.
  icons: {
    icon: [
      { url: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: { url: "/apple-touch-icon.png", sizes: "180x180", type: "image/png" },
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
