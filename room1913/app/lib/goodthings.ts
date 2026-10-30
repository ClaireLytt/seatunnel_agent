// Three Good Things — Seligman's classic evening exercise, kept per-browser
// in localStorage like lib/archive.ts and friends.

import { todayKey } from "./perma";

export interface GoodThing {
  text: string;
  why: string;
}

export interface GoodThingsEntry {
  day: string; // YYYY-MM-DD
  items: GoodThing[]; // exactly 3
  createdAt: number;
}

const KEY = "room1913.goodthings.v1";

export function loadGoodThings(): GoodThingsEntry[] {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function saveEntry(items: GoodThing[]): GoodThingsEntry[] {
  const list = loadGoodThings();
  const day = todayKey();
  const entry: GoodThingsEntry = { day, items, createdAt: Date.now() };
  const next = [...list.filter(e => e.day !== day), entry];
  try { localStorage.setItem(KEY, JSON.stringify(next)); } catch {}
  return next;
}

export function todayEntry(list: GoodThingsEntry[]): GoodThingsEntry | null {
  const day = todayKey();
  return list.find(e => e.day === day) ?? null;
}

// Consecutive days ending today (or yesterday, so the lamp does not go out
// before tonight's entry is written).
export function streakOf(list: GoodThingsEntry[]): number {
  const days = new Set(list.map(e => e.day));
  let streak = 0;
  const cursor = new Date();
  if (!days.has(todayKey(cursor))) cursor.setDate(cursor.getDate() - 1);
  while (days.has(todayKey(cursor))) {
    streak++;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
}
