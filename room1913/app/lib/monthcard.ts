// Month card — draw this month's garden onto a canvas and hand it over as
// a PNG: flowers in their pillar colors, the lamp streak, a few numbers.

import type { GoodNews, Pillar } from "./perma";
import { PILLAR_LABEL } from "./perma";
import type { GoodThingsEntry } from "./goodthings";

const PILLAR_COLOR: Record<Pillar, string> = {
  positive: "#d99a4e",
  engagement: "#c9b36a",
  relationships: "#9fb88a",
  meaning: "#b87a4a",
  accomplishment: "#e0cfa8",
};

export function drawMonthCard(
  history: GoodNews[],
  entries: GoodThingsEntry[],
  streak: number
): HTMLCanvasElement {
  const now = new Date();
  const ym = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  const monthNotes = history.filter(n => n.day.startsWith(ym));
  const monthNights = entries.filter(e => e.day.startsWith(ym)).length;

  const W = 640, H = 840;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d")!;

  // ground
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, "#15100b");
  bg.addColorStop(1, "#0c0906");
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = "rgba(217,154,78,0.35)";
  ctx.lineWidth = 2;
  ctx.strokeRect(18, 18, W - 36, H - 36);

  // title
  ctx.fillStyle = "rgba(232,220,196,0.94)";
  ctx.font = "44px Georgia, serif";
  ctx.textAlign = "center";
  ctx.fillText("ROOM 1913", W / 2, 110);
  ctx.font = "20px Georgia, serif";
  ctx.fillStyle = "rgba(217,154,78,0.8)";
  ctx.fillText(`${now.getFullYear()} 年 ${now.getMonth() + 1} 月的花园`, W / 2, 150);

  // flowerbed
  const baseY = 470;
  ctx.strokeStyle = "rgba(159,184,138,0.4)";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(80, baseY);
  ctx.lineTo(W - 80, baseY);
  ctx.stroke();

  const n = monthNotes.length;
  monthNotes.forEach((note, i) => {
    const x = n === 1 ? W / 2 : 110 + (i * (W - 220)) / Math.max(1, n - 1);
    const h = 80 + ((i * 29) % 70);
    const sway = ((i % 5) - 2) * 6;
    // stem
    ctx.strokeStyle = "rgba(159,184,138,0.55)";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(x, baseY);
    ctx.quadraticCurveTo(x + sway, baseY - h / 2, x, baseY - h);
    ctx.stroke();
    // petals
    const color = PILLAR_COLOR[note.pillar];
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.85;
    for (let a = 0; a < 5; a++) {
      const ang = (a * 2 * Math.PI) / 5 - Math.PI / 2;
      ctx.beginPath();
      ctx.ellipse(
        x + Math.cos(ang) * 11,
        baseY - h + Math.sin(ang) * 11,
        7, 11, ang + Math.PI / 2, 0, 2 * Math.PI
      );
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.fillStyle = "#1a140e";
    ctx.beginPath();
    ctx.arc(x, baseY - h, 5.5, 0, 2 * Math.PI);
    ctx.fill();
  });

  if (n === 0) {
    ctx.fillStyle = "rgba(232,220,196,0.4)";
    ctx.font = "italic 18px Georgia, serif";
    ctx.fillText("这个月的花坛还空着", W / 2, baseY - 60);
  }

  // numbers
  ctx.textAlign = "center";
  ctx.font = "19px Georgia, serif";
  ctx.fillStyle = "rgba(232,220,196,0.85)";
  const lines = [
    `种下了 ${n} 条好消息`,
    monthNights > 0 ? `记下了 ${monthNights} 晚的三件好事` : "",
    streak > 1 ? `油灯连续亮了 ${streak} 天` : "",
  ].filter(Boolean);
  lines.forEach((l, i) => ctx.fillText(l, W / 2, 560 + i * 40));

  // pillar legend
  const pillars = [...new Set(monthNotes.map(m => m.pillar))];
  if (pillars.length) {
    ctx.font = "14px Georgia, serif";
    const seg = pillars.map(p => PILLAR_LABEL[p].zh);
    pillars.forEach((p, i) => {
      const total = pillars.length;
      const x = W / 2 + (i - (total - 1) / 2) * 90;
      ctx.fillStyle = PILLAR_COLOR[p];
      ctx.beginPath();
      ctx.arc(x - 28, 706, 5, 0, 2 * Math.PI);
      ctx.fill();
      ctx.fillStyle = "rgba(232,220,196,0.7)";
      ctx.fillText(seg[i], x + 8, 711);
    });
  }

  // footer
  ctx.font = "13px Georgia, serif";
  ctx.fillStyle = "rgba(217,154,78,0.55)";
  ctx.fillText("· what was planted, the room remembers ·", W / 2, H - 56);

  return canvas;
}

export function downloadMonthCard(
  history: GoodNews[],
  entries: GoodThingsEntry[],
  streak: number
): void {
  const canvas = drawMonthCard(history, entries, streak);
  const now = new Date();
  const a = document.createElement("a");
  a.download = `room1913-garden-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}.png`;
  a.href = canvas.toDataURL("image/png");
  a.click();
}
