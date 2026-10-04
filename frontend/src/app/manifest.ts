import type { MetadataRoute } from "next";

// Home-screen and Android icons. Colours match --color-brand in globals.css.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "etika",
    short_name: "etika",
    description: "Compliance navigator for new Vancouver, BC businesses",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#2c4a21",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
