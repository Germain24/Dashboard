const INTERACTIVE_OVERLAY_SELECTOR = [
  '[role="dialog"]',
  '[role="alertdialog"]',
  '[role="menu"]',
  '[role="listbox"]',
  "dialog[open]",
  '[aria-modal="true"]',
  '[aria-haspopup="menu"][aria-expanded="true"]',
  '[aria-haspopup="dialog"][aria-expanded="true"]',
].join(",");

/** Returns whether an accessible interactive overlay is currently rendered. */
export function isInteractiveOverlayOpen(except?: Element | null): boolean {
  if (typeof document === "undefined") return false;

  return Array.from(document.querySelectorAll(INTERACTIVE_OVERLAY_SELECTOR)).some((overlay) => {
    if (overlay === except) return false;
    if (except?.contains(overlay) && overlay.getAttribute("role") === "listbox") return false;
    return !overlay.closest('[hidden], [inert], [aria-hidden="true"]');
  });
}
