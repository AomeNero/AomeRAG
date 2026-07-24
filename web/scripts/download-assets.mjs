// 下载 DeepSeek 站点静态资源（favicon / apple-touch-icon / og 图）
import fs from 'node:fs'
import path from 'node:path'

const targets = [
  { url: 'https://fe-static.deepseek.com/chat/favicon.svg', out: 'public/seo/favicon.svg' },
  { url: 'https://cdn.deepseek.com/chat/icon.png', out: 'public/seo/apple-touch-icon.png' },
  { url: 'https://cdn.deepseek.com/images/deepseek-chat-open-graph-image.jpeg', out: 'public/seo/og-image.jpeg' },
]

fs.mkdirSync('public/seo', { recursive: true })

for (const t of targets) {
  try {
    const res = await fetch(t.url, { headers: { 'User-Agent': 'Mozilla/5.0' } })
    if (!res.ok) { console.log(`FAIL ${res.status}  ${t.url}`); continue }
    const buf = Buffer.from(await res.arrayBuffer())
    fs.mkdirSync(path.dirname(t.out), { recursive: true })
    fs.writeFileSync(t.out, buf)
    console.log(`OK ${buf.length}B  ${t.out}`)
  } catch (e) {
    console.log(`ERR ${t.url}  ${e.message}`)
  }
}
