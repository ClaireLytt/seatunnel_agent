import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Room 1913",
    short_name: "Room 1913",
    description: "A midnight study, a quiet conversation across time.",
    start_url: "/garden",
    display: "standalone",
    background_color: "#0c0906",
    theme_color: "#0c0906",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
    ],
  };
}
