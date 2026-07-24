import { SignInForm } from './SignInForm'
import { WeChatCard } from './WeChatCard'

/** 落地/登录页（chat.deepseek.com/sign_in 未登录态） */
export function SignInPage({ onLogin }: { onLogin?: () => void }) {
  return (
    <div className="relative flex min-h-screen w-full flex-col items-center justify-center overflow-auto bg-background px-4">
      <div className="flex w-full max-w-[608px] flex-col items-center py-10">
        {/* Logo */}
        <div className="flex justify-center">
          <img src="/assets/logo-wordmark.svg" alt="DeepSeek" className="h-7 w-[182px]" />
        </div>

        {/* 双列：表单 + 微信卡（移动端单列堆叠） */}
        <div className="mt-10 flex w-full flex-col gap-5 md:flex-row md:gap-8">
          <SignInForm onLogin={onLogin} />
          <WeChatCard />
        </div>
      </div>

      {/* 页脚 */}
      <footer className="absolute bottom-0 left-0 right-0 flex justify-center pb-5 text-xs text-muted">
        <a
          href="https://beian.miit.gov.cn/"
          target="_blank"
          rel="noreferrer"
          className="text-brand hover:underline"
        >
          浙ICP备2023025841号
        </a>
        <span className="mx-1">·</span>
        <a
          href="https://trtgsjkv6r.feishu.cn/share/base/form/shrcnhcHE4A6lQaQ3v0raCXmBAg"
          target="_blank"
          rel="noreferrer"
          className="text-brand hover:underline"
        >
          联系我们
        </a>
      </footer>
    </div>
  )
}
