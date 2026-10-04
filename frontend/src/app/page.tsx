import { Geist, Geist_Mono } from "next/font/google";
import { Landing } from "@/components/landing/Landing";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono" });

export default function Home() {
  return (
    <div className={`${geist.variable} ${geistMono.variable}`}>
      <Landing />
    </div>
  );
}
