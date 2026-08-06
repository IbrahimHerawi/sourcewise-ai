import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "SourceWise",
    short_name: "SourceWise",
    description:
      "Ask questions and get cited AI answers grounded in your own documents.",
    start_url: "/",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#4679f9",
    icons: [
      {
        src: "/brand/sourcewise-mark-192.png",
        sizes: "192x192",
        type: "image/png",
      },
      {
        src: "/brand/sourcewise-mark-512.png",
        sizes: "512x512",
        type: "image/png",
      },
    ],
  };
}
