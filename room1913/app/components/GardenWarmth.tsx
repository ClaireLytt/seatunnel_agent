"use client";
import { useEffect } from "react";
import { GoodNews } from "../lib/perma";

// Lets the kept garden reach the weather: the more good news in the last
// seven days, the softer the rain and the warmer the window.

const CLIENT_KEY = "room1913.garden.client.v1";
const WEEK = 7 * 24 * 60 * 60 * 1000;

export default function GardenWarmth() {
  useEffect(() => {
    let clientId = "";
    try { clientId = localStorage.getItem(CLIENT_KEY) ?? ""; } catch {}
    if (!clientId) return;
    fetch(`/api/goodnews?clientId=${encodeURIComponent(clientId)}`)
      .then(r => r.json())
      .then(d => {
        const history: GoodNews[] = Array.isArray(d.history) ? d.history : [];
        const recent = history.filter(n => Date.now() - n.createdAt < WEEK).length;
        const warmth = recent >= 3 ? "2" : recent >= 1 ? "1" : "0";
        document.documentElement.dataset.warmth = warmth;
      })
      .catch(() => {});
  }, []);
  return null;
}
