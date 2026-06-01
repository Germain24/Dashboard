import { ReactNode } from "react";

interface PageLayoutProps {
  title: string;
  actions?: ReactNode;
  children: ReactNode;
}

export default function PageLayout({ title, actions, children }: PageLayoutProps) {
  return (
    <div className="flex flex-col min-h-full">
      <div className="flex items-center justify-between px-6 py-5 border-b border-[var(--border)] animate-fade-in">
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {actions && <div className="flex items-center gap-2">{actions}</div>}
      </div>
      <div className="flex-1 p-6 animate-fade-in-up">
        {children}
      </div>
    </div>
  );
}
