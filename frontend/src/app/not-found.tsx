import Link from "next/link";

/** Page 404 (App Router). */
export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <p className="text-4xl font-bold tracking-tight">404</p>
      <p className="text-sm text-[var(--muted-foreground)]">Cette page n&apos;existe pas.</p>
      <Link
        href="/"
        className="rounded-md bg-[var(--primary)] px-4 py-2 text-sm font-medium text-[var(--primary-foreground)] hover:opacity-90"
      >
        Retour à l&apos;accueil
      </Link>
    </div>
  );
}
