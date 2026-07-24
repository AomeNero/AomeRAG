// 处理聊天界面提取结果：保存 SVG、产出精简结构、打印主题色摘要
import fs from 'node:fs'
import path from 'node:path'

const rawPath = process.argv[2]
const svgDir = 'public/assets/chat'
let raw = fs.readFileSync(rawPath, 'utf8').trim()
let obj
try { const inner = JSON.parse(raw); obj = typeof inner === 'string' ? JSON.parse(inner) : inner } catch { obj = JSON.parse(raw) }

fs.mkdirSync(svgDir, { recursive: true })
fs.mkdirSync('docs/research', { recursive: true })

// 保存 SVG（按尺寸去重）
const seen = new Set()
const svgFiles = []
if (Array.isArray(obj.svgs)) {
  obj.svgs.forEach((s, i) => {
    const key = s.w + 'x' + s.h + ':' + s.html.length
    if (seen.has(key)) return
    seen.add(key)
    const name = s.w >= 120 ? 'chat-logo' : `icon-${s.w}x${s.h}-${i}`
    const file = path.join(svgDir, `${name}.svg`)
    fs.writeFileSync(file, s.html + '\n', 'utf8')
    svgFiles.push({ file: file.replace(/\\/g, '/'), w: s.w, h: s.h })
  })
}

// 精简侧边栏结构（svg 已是叶子）写到文件
if (obj.sidebar) fs.writeFileSync('docs/research/chat-sidebar.json', JSON.stringify(obj.sidebar, null, 1), 'utf8')

// 摘要（stdout，小）
const sb = obj.sidebar
console.log(JSON.stringify({
  topBg: obj.topBg,
  topColors: obj.topColors,
  svgCount: obj.svgCount,
  svgSaved: svgFiles,
  sidebar: sb ? { w: sb.w, h: sb.h, bg: sb.s?.bg, pad: sb.s?.pad, childCount: sb.k?.length, children: (sb.k || []).map(c => ({ w: c.w, h: c.h, tx: c.tx, bg: c.s?.bg, br: c.s?.br, cls: c.t })) } : null,
}, null, 1))
