// 处理 agent-browser eval 的大输出：剥离 svg path 子节点、保存 SVG 资源、产出精简结构 JSON
import fs from 'node:fs'
import path from 'node:path'

const rawPath = process.argv[2]
const outDir = process.argv[3] || 'public/assets'
let raw = fs.readFileSync(rawPath, 'utf8').trim()

// agent-browser eval 的输出是 JSON 编码的字符串（可能双重编码）
let obj
try {
  const inner = JSON.parse(raw)
  obj = typeof inner === 'string' ? JSON.parse(inner) : inner
} catch {
  obj = JSON.parse(raw)
}

fs.mkdirSync(outDir, { recursive: true })
fs.mkdirSync('docs/research', { recursive: true })

// 1) 保存 SVG
const svgFiles = []
if (Array.isArray(obj.svgs)) {
  obj.svgs.forEach((s, i) => {
    const isLogo = s.w >= 150 // 字标 logo 较宽
    const name = isLogo ? 'logo-wordmark' : `icon-${i}-${s.w}x${s.h}`
    const file = path.join(outDir, `${name}.svg`)
    fs.writeFileSync(file, s.html + '\n', 'utf8')
    svgFiles.push({ file, w: s.w, h: s.h, bytes: s.html.length })
  })
}

// 2) 清理 card 结构：svg 节点只保留尺寸
function clean(node) {
  if (!node || typeof node !== 'object') return node
  if (node.t === 'svg') return { t: 'svg', w: node.w, h: node.h }
  if (node.k) node.k = node.k.map(clean)
  return node
}
if (obj.card) clean(obj.card)

fs.writeFileSync('docs/research/sign-in-card-structure.json', JSON.stringify(obj.card, null, 1), 'utf8')

// 3) 小摘要
const summary = {
  card: obj.card ? { w: obj.card.w, h: obj.card.h, pad: obj.card.s?.padding, display: obj.card.s?.display } : null,
  svgFiles,
  childCount: obj.card?.k?.length || 0,
}
console.log(JSON.stringify(summary, null, 1))
