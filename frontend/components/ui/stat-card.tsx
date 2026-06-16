interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'neutral'
  color?: 'default' | 'success' | 'danger' | 'info'
}

export function StatCard({ label, value, sub, trend, color = 'default' }: StatCardProps) {
  const colors = {
    default: 'text-[var(--foreground)]',
    success: 'text-[var(--success)]',
    danger: 'text-[var(--destructive)]',
    info: 'text-[var(--ring)]',
  }
  const trendIcon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : ''

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.4] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] p-5 card-hover space-y-1">
      <p className="text-[13px] text-[var(--muted-foreground)]">{label}</p>
      <p className={`font-display text-[1.75rem] leading-tight tabular-nums ${colors[color]}`}>
        {value}
        {trendIcon && <span className="ml-1.5 text-base opacity-60">{trendIcon}</span>}
      </p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  )
}
