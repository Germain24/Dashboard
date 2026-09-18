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
  return (
    <div className="glass-card rounded-[var(--radius-lg)] p-5 card-hover space-y-1">
      <p className="text-[13px] text-[var(--muted-foreground)]">{label}</p>
      <p className={`font-display text-[1.75rem] leading-tight tabular-nums ${colors[color]}`}>
        <StatValue value={value} />
        <TrendIndicator trend={trend} />
      </p>
      {sub && <p className="text-xs text-[var(--muted-foreground)]">{sub}</p>}
    </div>
  )
}

function TrendIndicator({ trend }: { trend?: StatCardProps['trend'] }) {
  const icon = trend === 'up' ? '↑' : trend === 'down' ? '↓' : '';
  if (!icon) return null;
  return <span className="ml-1.5 text-base opacity-60">{icon}</span>;
}

function StatValue({ value }: { value: string | number }) {
  if (typeof value !== 'number') return <>{value}</>;
  return (
    <AnimatedNumber
      value={value}
      format={(current) =>
        current.toLocaleString('fr-CA', {
          minimumFractionDigits: decimalPlaces(value),
          maximumFractionDigits: decimalPlaces(value),
        })
      }
    />
  );
}

function decimalPlaces(value: number) {
  if (Number.isInteger(value)) return 0;
  return String(value).split('.')[1]?.length ?? 0;
}
