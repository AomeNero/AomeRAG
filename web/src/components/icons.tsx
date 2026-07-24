import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

/** 微信图标（来自 DeepSeek 站点提取，fill=currentColor） */
export function WeChatIcon(props: IconProps) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M9.5 4C5.36 4 2 6.69 2 10c0 1.89 1.08 3.56 2.78 4.66L4 17l2.5-1.5c.89.31 1.87.5 2.91.5A5.22 5.22 0 0 1 9 14c0-3.31 3.13-6 7-6c.19 0 .38 0 .56.03C15.54 5.69 12.78 4 9.5 4m-3 2.5a1 1 0 0 1 1 1a1 1 0 0 1-1 1a1 1 0 0 1-1-1a1 1 0 0 1 1-1m5 0a1 1 0 0 1 1 1a1 1 0 0 1-1 1a1 1 0 0 1-1-1a1 1 0 0 1 1-1M16 9c-3.31 0-6 2.24-6 5s2.69 5 6 5c.67 0 1.31-.08 1.91-.25L20 20l-.62-1.87C20.95 17.22 22 15.71 22 14c0-2.76-2.69-5-6-5m-2 2.5a1 1 0 0 1 1 1a1 1 0 0 1-1 1a1 1 0 0 1-1-1a1 1 0 0 1 1-1m4 0a1 1 0 0 1 1 1a1 1 0 0 1-1 1a1 1 0 0 1-1-1a1 1 0 0 1 1-1" />
    </svg>
  )
}

/** 勾选（微信已扫码状态，渲染为绿色） */
export function CheckIcon(props: IconProps) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M20 6 9 17l-5-5" />
    </svg>
  )
}

/** 占位二维码（DeepSeek 微信二维码为跨域会话相关，用近似 QR 图案占位） */
export function QrPlaceholderIcon(props: IconProps) {
  const N = 25
  const inFinder = (x: number, y: number) =>
    (x < 8 && y < 8) || (x >= N - 8 && y < 8) || (x < 8 && y >= N - 8)

  const finder = (fx: number, fy: number): ReactNode => (
    <g key={`f-${fx}-${fy}`}>
      <rect x={fx} y={fy} width={7} height={7} />
      <rect x={fx + 1} y={fy + 1} width={5} height={5} fill="#f9fafb" />
      <rect x={fx + 2} y={fy + 2} width={3} height={3} />
    </g>
  )

  const cells: ReactNode[] = []
  for (let y = 0; y < N; y++) {
    for (let x = 0; x < N; x++) {
      if (inFinder(x, y)) continue
      if ((x * 7 + y * 13 + x * y * 3) % 5 < 2) {
        cells.push(<rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} />)
      }
    }
  }

  return (
    <svg viewBox={`0 0 ${N} ${N}`} fill="currentColor" shapeRendering="crispEdges" {...props}>
      {cells}
      {finder(0, 0)}
      {finder(N - 7, 0)}
      {finder(0, N - 7)}
    </svg>
  )
}
