import { useState, type ReactNode } from 'react'
import { cn } from '../lib/utils'

type Mode = 'code' | 'password'

/** 左列：登录表单（验证码 / 密码 两种模式） */
export function SignInForm({ onLogin }: { onLogin?: () => void }) {
  const [mode, setMode] = useState<Mode>('code')
  const [phone, setPhone] = useState('')
  const [credential, setCredential] = useState('') // 验证码或密码
  const [countdown, setCountdown] = useState(0)

  const sendCode = () => {
    if (countdown > 0) return
    setCountdown(60)
    const timer = setInterval(() => {
      setCountdown((c) => {
        if (c <= 1) {
          clearInterval(timer)
          return 0
        }
        return c - 1
      })
    }, 1000)
  }

  const toggleMode = () => setMode((m) => (m === 'code' ? 'password' : 'code'))

  return (
    <div className="w-full md:w-[336px] md:flex-1">
      <div className="flex flex-col">
        {/* 手机号字段 */}
        <FieldRow>
          <div
            className={cn(
              'flex h-12 w-full items-center rounded-full border border-line bg-field transition-colors focus-within:border-brand',
              mode === 'code' ? 'px-2.5' : 'px-4',
            )}
          >
            {mode === 'code' && <span className="shrink-0 text-foreground">+86</span>}
            <input
              type={mode === 'code' ? 'tel' : 'text'}
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder={mode === 'code' ? '请输入手机号' : '请输入手机号/邮箱地址'}
              className="h-full flex-1 bg-transparent px-1.5 text-sm text-foreground outline-none placeholder:text-placeholder"
            />
          </div>
        </FieldRow>

        {/* 验证码 / 密码字段 */}
        <FieldRow>
          <div className="flex h-12 w-full items-center rounded-full border border-line bg-field px-4 pr-5 transition-colors focus-within:border-brand">
            {mode === 'code' ? (
              <>
                <input
                  type="tel"
                  value={credential}
                  onChange={(e) => setCredential(e.target.value)}
                  placeholder="请输入验证码"
                  className="h-full flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-placeholder"
                />
                <span className="mx-3 h-5 w-px shrink-0 bg-line" />
                <button
                  type="button"
                  onClick={sendCode}
                  disabled={countdown > 0}
                  className="shrink-0 text-sm text-brand disabled:opacity-60"
                >
                  {countdown > 0 ? `${countdown}s` : '发送验证码'}
                </button>
              </>
            ) : (
              <input
                type="password"
                value={credential}
                onChange={(e) => setCredential(e.target.value)}
                placeholder="请输入密码"
                className="h-full flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-placeholder"
              />
            )}
          </div>
        </FieldRow>

        {/* 协议 */}
        <p className="px-0.5 pb-1 pt-1 text-xs leading-[18px] text-muted">
          注册登录即代表已阅读并同意我们的{' '}
          <a className="text-foreground hover:underline" href="#" onClick={(e) => e.preventDefault()}>
            用户协议
          </a>{' '}
          与{' '}
          <a className="text-foreground hover:underline" href="#" onClick={(e) => e.preventDefault()}>
            隐私政策
          </a>
          ，未注册的手机号将自动注册
        </p>

        {/* 登录按钮 */}
        <button
          type="button"
          onClick={onLogin}
          className="mt-1 h-[42px] w-full rounded-full bg-brand text-sm font-medium text-white transition hover:brightness-95 active:scale-[0.99]"
        >
          登录
        </button>

        {/* 次级登录 */}
        <div className="mt-3 flex items-center justify-center gap-2 text-xs text-muted">
          <button
            type="button"
            onClick={toggleMode}
            className="rounded-full px-2 py-1 transition hover:bg-black/5"
          >
            {mode === 'code' ? '密码登录' : '验证码登录'}
          </button>
          <span className="h-3 w-px bg-line" />
          <button type="button" className="rounded-full px-2 py-1 transition hover:bg-black/5">
            使用 Apple 账号登录
          </button>
        </div>
      </div>
    </div>
  )
}

/** 字段行：输入框(48) + 辅助文案槽(22) */
function FieldRow({ children }: { children: ReactNode }) {
  return (
    <div>
      {children}
      <div className="h-[22px]" />
    </div>
  )
}
