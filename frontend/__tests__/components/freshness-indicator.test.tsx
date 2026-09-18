import { act } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { FreshnessIndicator } from "@/components/FreshnessIndicator";

function App({ client }: { client: QueryClient }) {
  return (
    <QueryClientProvider client={client}>
      <FreshnessIndicator />
    </QueryClientProvider>
  );
}

describe("FreshnessIndicator hydration", () => {
  it("produit un emplacement SSR stable puis s'hydrate sans mismatch", async () => {
    const client = new QueryClient();
    const html = renderToString(<App client={client} />);
    expect(html).toContain("invisible");
    const container = document.createElement("div");
    container.innerHTML = html;
    const error = vi.spyOn(console, "error").mockImplementation(() => undefined);

    await act(async () => {
      hydrateRoot(container, <App client={client} />);
    });

    expect(error.mock.calls.flat().join(" ")).not.toMatch(/hydration|did not match/i);
    error.mockRestore();
  });
});
