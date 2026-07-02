import { AnimatedNumber } from '@/lib/motion/AnimatedNumber'

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

  // Count-up seulement pour les nombres ; on fige le nombre de décimales de
  // la cible pour que le format ne « saute » pas pendant l'animation.
  const decimals =
    typeof value === 'number' && !Number.isInteger(value)
      ? (String(value).split('.')[1]?.length ?? 0)
      : 0
  const formatted =
    typeof value === 'number' ? (
      <AnimatedNumber
        value={value}
        format={(v) =>
          v.toLocaleString('fr-CA', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          })
        }
      />
    ) : (
      value
    )

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--glass-border)] bg-[var(--card)] backdrop-blur-[var(--glass-blur)] backdrop-saturate-[1.4] shadow-[inset_0_1px_0_0_var(--glass-highlight),var(--shadow)] p-5 card-hover space-y-1">
      <p className="text-[13px] text-[var(--muted-foreground)]">{label}</p>
      <p className={`font-display text-[1.75rem] leading-tight tabular-nums ${colors[color]}`}>
        {formatted}
        {trendIcon && <span className="ml-1.5 text-base opacity-60">{trendIcon}</span>}
      </p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  )
}
