import { NextResponse } from "next/server";
import { readCollection, writeCollection } from "@/app/lib/store";

export const runtime = "nodejs";

// Bottle post: a line written for whoever opens this room late at night,
// cast into the rain and washed up for another visitor. Anonymous, random,
// not bound to a day or a pillar.

interface Bottle {
  id: string;
  clientId: string;
  text: string;
  createdAt: number;
}

const SEEDS: string[] = [
  "凌晨打开这个房间的人，愿你的台灯和我的一样暖。",
  "今天也没什么大事发生，这本身就是一件好事。",
  "你现在想不通的事，三个月后多半想不起来。",
  "雨会停的。停不了的话，就听着它睡。",
  "谢谢你也在深夜认真地生活。",
  "把今天过完就好，明天的事交给明天的你。",
];

const loadBottles = () => readCollection<Bottle>("bottles");

function pickForMe(list: Bottle[], clientId: string): { text: string } | null {
  const others = list.filter(b => b.clientId !== clientId);
  if (others.length) {
    return { text: others[Math.floor(Math.random() * others.length)].text };
  }
  return { text: SEEDS[Math.floor(Math.random() * SEEDS.length)] };
}

export async function POST(req: Request) {
  try {
    const body = (await req.json()) as { text?: string; clientId?: string };
    const text = String(body.text ?? "").trim().slice(0, 200);
    const clientId = String(body.clientId ?? "").trim().slice(0, 64);
    if (!text || !clientId) {
      return NextResponse.json({ error: "empty bottle" }, { status: 400 });
    }
    const list = await loadBottles();
    list.push({
      id: `bt-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      clientId,
      text,
      createdAt: Date.now(),
    });
    await writeCollection("bottles", list);
    return NextResponse.json({ cast: true, received: pickForMe(list, clientId) });
  } catch (err) {
    console.error("bottle error", err);
    return NextResponse.json({ error: "the bottle sank" }, { status: 500 });
  }
}
