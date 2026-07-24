// 聊天界面提取脚本（侧边栏 + 主题色 + 所有 SVG）。输出会被重定向到文件后用 Node 处理。
(function () {
  const PURPLE = 'rgb(128, 0, 128)';
  function pick(el) {
    const c = getComputedStyle(el); const o = {};
    const add = (k, p) => { const v = c[p]; if (v && v !== 'none' && v !== 'normal' && v !== 'auto' && v !== '0px' && v !== 'rgba(0, 0, 0, 0)' && v !== '0' && v !== PURPLE && v !== 'rgb(0, 0, 0)') o[k] = v; };
    ['display', 'flexDirection', 'alignItems', 'justifyContent', 'gap', 'width', 'height', 'position', 'backgroundColor', 'borderRadius', 'border', 'color', 'fontSize', 'fontWeight', 'overflow', 'padding', 'marginTop'].forEach(p => {
      const k = { flexDirection: 'fd', alignItems: 'ai', justifyContent: 'jc', backgroundColor: 'bg', borderRadius: 'br', border: 'bdr', fontSize: 'fs', fontWeight: 'fw', overflow: 'ow', padding: 'pad', marginTop: 'mt' }[p] || p;
      add(k, p);
    });
    return o;
  }
  function walk(el, d) {
    if (!el || d > 6) return null;
    if (el.tagName === 'SVG') return { t: 'svg', w: Math.round(el.getBoundingClientRect().width), h: Math.round(el.getBoundingClientRect().height) };
    const kids = [...el.children].filter(c => c && c.tagName && !['SCRIPT', 'STYLE', 'LINK', 'IFRAME'].includes(c.tagName));
    const r = el.getBoundingClientRect();
    const onlyTxt = el.childNodes.length === 1 && el.childNodes[0].nodeType === 3;
    let tx = onlyTxt ? el.textContent.trim().slice(0, 30) : null;
    if ((el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') && el.placeholder) tx = '[' + el.placeholder + ']';
    return { t: el.tagName.toLowerCase(), w: Math.round(r.width), h: Math.round(r.height), tx, s: pick(el), k: kids.slice(0, 12).map(c => walk(c, d + 1)).filter(Boolean) };
  }
  // 主题色统计
  const all = [...document.querySelectorAll('*')].slice(0, 500);
  const bgCount = {}, colorCount = {};
  all.forEach(e => { const c = getComputedStyle(e); if (c.backgroundColor && c.backgroundColor !== 'rgba(0, 0, 0, 0)') bgCount[c.backgroundColor] = (bgCount[c.backgroundColor] || 0) + 1; if (c.color && c.color !== PURPLE && c.color !== 'rgb(0, 0, 0)') colorCount[c.color] = (colorCount[c.color] || 0) + 1; });
  const topBg = Object.entries(bgCount).sort((a, b) => b[1] - a[1]).slice(0, 8);
  const topColors = Object.entries(colorCount).sort((a, b) => b[1] - a[1]).slice(0, 8);
  // 侧边栏
  const sidebar = document.querySelector('.b8812f16');
  // SVG
  const svgs = [...document.querySelectorAll('svg')].map(s => ({ w: Math.round(s.getBoundingClientRect().width), h: Math.round(s.getBoundingClientRect().height), html: s.outerHTML.replace(/\n/g, ' ') }));
  return JSON.stringify({ topBg, topColors, sidebar: sidebar ? walk(sidebar, 0) : null, svgCount: svgs.length, svgs }, null, 1);
})();
