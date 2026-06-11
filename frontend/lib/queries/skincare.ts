"use client";

/** Couche TanStack Query du module Skincare (#531). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { skincareApi, type SkincareProduct } from "@/lib/skincare";

export const skincareKeys = {
  all: ["skincare"] as const,
  products: () => [...skincareKeys.all, "products"] as const,
  today: () => [...skincareKeys.all, "today"] as const,
  toRepurchase: () => [...skincareKeys.all, "to-repurchase"] as const,
};

export function useSkincareProducts() {
  return useQuery({ queryKey: skincareKeys.products(), queryFn: skincareApi.list });
}
export function useSkincareToday() {
  return useQuery({ queryKey: skincareKeys.today(), queryFn: skincareApi.today });
}
export function useToRepurchase() {
  return useQuery({ queryKey: skincareKeys.toRepurchase(), queryFn: skincareApi.toRepurchase });
}

function useInvalidateAll() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: skincareKeys.all });
}

export function useCreateSkincareProduct() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (d: Partial<SkincareProduct>) => skincareApi.create(d),
    onSuccess: invalidate,
  });
}
export function useUpdateSkincareProduct() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (p: { id: number; patch: Partial<SkincareProduct> }) =>
      skincareApi.update(p.id, p.patch),
    onSuccess: invalidate,
  });
}
export function useDeleteSkincareProduct() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => skincareApi.remove(id), onSuccess: invalidate });
}
