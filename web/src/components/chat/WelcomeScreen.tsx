export function WelcomeScreen() {
  return (
    <div className="flex flex-col items-center px-4 text-center">
      <h1 className="text-[28px] font-semibold text-foreground">你好，我是 AomeRAG</h1>
      <p className="mt-3 text-sm leading-6 text-muted">
        基于公司知识库问答。先点左下角「导入知识库」喂入文档，再向我提问。
      </p>
    </div>
  )
}
