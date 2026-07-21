import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { QueryProvider } from "@/components/QueryProvider";

describe("QueryProvider", () => {
  it("supprime l'ancien cache persistant contenant des données privées", () => {
    localStorage.setItem("mc-query-cache", JSON.stringify({ private: true }));

    render(
      <QueryProvider>
        <div>contenu</div>
      </QueryProvider>,
    );

    expect(screen.getByText("contenu")).toBeInTheDocument();
    expect(localStorage.getItem("mc-query-cache")).toBeNull();
  });
});
