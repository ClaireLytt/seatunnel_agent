"use client";
import { useEffect } from "react";

// The window follows the visitor's real season: a quiet shift of color
// temperature, nothing more. Autumn is the room's native key.
export default function Seasons() {
  useEffect(() => {
    const m = new Date().getMonth() + 1;
    const season =
      m >= 3 && m <= 5 ? "spring" :
      m >= 6 && m <= 8 ? "summer" :
      m >= 9 && m <= 11 ? "autumn" : "winter";
    document.documentElement.dataset.season = season;
  }, []);
  return null;
}
