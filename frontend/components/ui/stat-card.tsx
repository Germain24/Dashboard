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
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-5 card-hover space-y-1">
      <p className="text-xs font-medium text-[var(--muted-foreground)] uppercase tracking-wider">{label}</p>
      <p className={`text-2xl font-bold font-mono ${colors[color]}`}>
        {value}
        {trendIcon && <span className="text-sm ml-1 opacity-70">{trendIcon}</span>}
      </p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  )
}
