import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import {
  SkeletonHeader,
  SkeletonStatRow,
  SkeletonCardGrid,
  SkeletonList,
} from "@/components/ui/skeleton";
import PageSkeleton from "@/components/PageSkeleton";

describe("blocs skeleton", () => {
  it("SkeletonStatRow rend n cartes", () => {
    const { container } = render(<SkeletonStatRow count={4} />);
    expect(container.querySelectorAll("[data-skeleton='stat']")).toHaveLength(4);
  });

  it("SkeletonCardGrid rend n cartes", () => {
    const { container } = render(<SkeletonCardGrid count={8} cols={4} />);
    expect(container.querySelectorAll("[data-skeleton='card']")).toHaveLength(8);
  });

  it("SkeletonList rend n lignes", () => {
    const { container } = render(<SkeletonList rows={6} />);
    expect(container.querySelectorAll("[data-skeleton='row']")).toHaveLength(6);
  });

  it("SkeletonHeader rend titre + sous-titre", () => {
    const { container } = render(<SkeletonHeader />);
    expect(container.querySelectorAll(".skeleton-shimmer").length).toBeGreaterThanOrEqual(2);
  });

  it("PageSkeleton = header + stats + grille", () => {
    const { container } = render(<PageSkeleton />);
    expect(container.querySelectorAll("[data-skeleton='stat']")).toHaveLength(3);
    expect(container.querySelectorAll("[data-skeleton='card']")).toHaveLength(6);
  });
});
