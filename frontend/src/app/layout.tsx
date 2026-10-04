import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "etika",
  description: "Compliance navigator for new Vancouver, BC businesses",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
