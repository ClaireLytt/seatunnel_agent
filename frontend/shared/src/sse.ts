// POST + server-sent-events reader: parses `data: <json>` frames and hands
// each parsed event to the callback. Throws on non-2xx with the body text.
export async function postSSE<E>(
  url: string,
  body: unknown,
  onEvent: (e: E) => void,
): Promise<void> {
  const r = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok || !r.body) {
    const detail = await r.text().catch(() => '')
    throw new Error(`HTTP ${r.status} ${detail}`)
  }
  const reader = r.body.getReader()
  const decoder = new TextDecoder()
  let buf = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx)
      buf = buf.slice(idx + 2)
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) onEvent(JSON.parse(line.slice(6)) as E)
      }
    }
  }
}
