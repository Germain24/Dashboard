interface PageLayoutProps {
  title: string
  actions?: React.ReactNode
  children: React.ReactNode
}

export function PageLayout({ title, actions, children }: PageLayoutProps) {
  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Header */}
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold tracking-tight text-[var(--foreground)]">
          {title}
        </h1>
        {actions && (
          <div className="flex items-center gap-2 shrink-0">
            {actions}
          </div>
        )}
      </header>

      {/* Content */}
      <div>{children}</div>
    </div>
  )
}
