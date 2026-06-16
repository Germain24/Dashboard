import { ReactNode } from "react";

interface PageLayoutProps {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}

export default function PageLayout({ title, actions, children }: PageLayoutProps) {
  return (
    <div className="flex flex-col min-h-full">
      {/* En-tête collant en verre : le contenu glisse dessous au scroll. */}
      <div className="glass-panel sticky top-0 z-[var(--z-header)] flex items-center justify-between border-b border-[var(--glass-border)] px-6 py-4 animate-fade-in">
        <h1 className="font-display text-2xl text-[var(--foreground)]">{title}</h1>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <div className="flex-1 p-6 animate-fade-in-up">
        {children}
      </div>
    </div>
  );
}
