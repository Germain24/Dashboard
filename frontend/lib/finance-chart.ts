type CapitalPoint = {
  investit: number;
};

/**
 * Repère les changements de périmètre assez importants pour qu'une ligne
 * continue suggère à tort une performance ou une perte de marché.
 */
export function capitalBreakIndexes(
  history: CapitalPoint[],
  relativeThreshold = 0.5,
  minimumCapital = 5_000,
): number[] {
  const indexes: number[] = [];
  for (let index = 1; index < history.length; index += 1) {
    const previous = Math.abs(history[index - 1]?.investit ?? 0);
    const current = Math.abs(history[index]?.investit ?? 0);
    if (Math.max(previous, current) < minimumCapital) continue;
    const relativeChange = Math.abs(current - previous) / Math.max(previous, 1);
    if (relativeChange > relativeThreshold) indexes.push(index);
  }
  return indexes;
}
