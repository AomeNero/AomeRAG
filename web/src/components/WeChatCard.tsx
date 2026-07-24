import { CheckIcon, QrPlaceholderIcon, WeChatIcon } from './icons'

/** 右列：微信扫码登录卡（二维码为跨域会话相关，用占位 QR） */
export function WeChatCard() {
  return (
    <div className="w-full md:w-[240px] md:flex-none">
      <div className="flex h-full min-h-[266px] flex-col rounded-[10px] border border-line bg-field pb-6 pt-[38px]">
        {/* 二维码区 */}
        <div className="flex h-[160px] items-center justify-center">
          <QrPlaceholderIcon className="h-[124px] w-[124px] text-foreground" />
        </div>
        {/* 标签 */}
        <div className="mt-auto flex items-center justify-center gap-1.5 text-sm text-foreground">
          <WeChatIcon className="h-5 w-5" />
          <span>微信扫码登录</span>
          <CheckIcon className="h-5 w-5 text-wechat" />
        </div>
      </div>
    </div>
  )
}
