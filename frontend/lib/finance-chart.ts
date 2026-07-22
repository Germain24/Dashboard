type CapitalPoint = {
  investit: number;
};

type DatedCapitalPoint = CapitalPoint & {
  date: string;
};

type DatedValuePoint = {
  date: string;
  valeur: number;
};

type CashFlow = {
  day: number;
  amount: number;
};

const DAYS_PER_YEAR = 365.25;
const MILLISECONDS_PER_DAY = 86_400_000;

function utcDay(date: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T)/.exec(date);
  if (!match) return null;

  const year = Number(match[1]);
  const month = Number(match[2]);
  const dayOfMonth = Number(match[3]);
  const timestamp = Date.UTC(year, month - 1, dayOfMonth);
  const parsed = new Date(timestamp);
  if (
    !Number.isFinite(timestamp) ||
    parsed.getUTCFullYear() !== year ||
    parsed.getUTCMonth() !== month - 1 ||
    parsed.getUTCDate() !== dayOfMonth
  ) {
    return null;
  }
  return timestamp / MILLISECONDS_PER_DAY;
}

function solveXirr(cashFlows: CashFlow[]): number | null {
  const byDay = new Map<number, number>();
  for (const { day, amount } of cashFlows) {
    if (!Number.isFinite(day) || !Number.isFinite(amount)) continue;
    byDay.set(day, (byDay.get(day) ?? 0) + amount);
  }

  const dated = [...byDay.entries()]
    .filter(([, amount]) => Math.abs(amount) >= 0.005)
    .sort(([left], [right]) => left - right);
  if (dated.length < 2) return null;

  const amounts = dated.map(([, amount]) => amount);
  if (!amounts.some((amount) => amount < 0) || !amounts.some((amount) => amount > 0)) {
    return null;
  }

  const origin = dated[0][0];
  const scale = Math.max(...amounts.map(Math.abs));
  const npv = (rate: number) => {
    if (rate <= -1) return Number.NaN;
    const logBase = Math.log1p(rate);
    return dated.reduce(
      (total, [day, amount]) =>
        total + (amount / scale) * Math.exp(-((day - origin) / DAYS_PER_YEAR) * logBase),
      0,
    );
  };

  const hasOppositeSigns = (left: number, right: number) =>
    left === 0 || right === 0 || Math.sign(left) !== Math.sign(right);

  let low = -0.999999;
  let high = 1;
  let lowValue = npv(low);
  let highValue = npv(high);
  if (Number.isNaN(lowValue) || Number.isNaN(highValue)) return null;

  while (!hasOppositeSigns(lowValue, highValue) && high < 1_000_000) {
    high = high * 2 + 1;
    highValue = npv(high);
    if (Number.isNaN(highValue)) return null;
  }
  if (!hasOppositeSigns(lowValue, highValue)) return null;

  for (let iteration = 0; iteration < 200; iteration += 1) {
    const middle = (low + high) / 2;
    const middleValue = npv(middle);
    if (Number.isNaN(middleValue)) return null;
    if (Math.abs(middleValue) < 1e-12 || high - low < 1e-12) return middle;

    if (hasOppositeSigns(lowValue, middleValue)) {
      high = middle;
    } else {
      low = middle;
      lowValue = middleValue;
    }
  }

  return (low + high) / 2;
}

/** Annualise le multiple valeur finale / capital net sur la durée exacte. */
export function annualizedCapitalReturn(
  finalValue: number,
  invested: number,
  startDate: string,
  endDate: string,
): number | null {
  const start = utcDay(startDate);
  const end = utcDay(endDate);
  if (start == null || end == null) return null;
  const days = end - start;
  if (days <= 0 || finalValue <= 0 || invested <= 0) return null;
  const result = (Math.pow(finalValue / invested, DAYS_PER_YEAR / days) - 1) * 100;
  return Number.isFinite(result) ? result : null;
}

/**
 * Calcule le TRI/XIRR annualisé d'une série de valeurs avec les apports datés.
 *
 * La première valeur est le capital d'ouverture, les variations ultérieures de
 * `investit` sont des flux externes, puis la dernière valeur liquide virtuellement
 * le portefeuille. Une donnée de capital manquante est donc reportée constante.
 */
export function moneyWeightedAnnualizedReturn(
  values: DatedValuePoint[],
  capitalHistory: DatedCapitalPoint[],
): number | null {
  const valuesByDay = new Map<number, number>();
  for (const point of values) {
    const day = utcDay(point.date);
    if (day != null && Number.isFinite(point.valeur)) valuesByDay.set(day, point.valeur);
  }
  const preparedValues = [...valuesByDay.entries()].sort(([left], [right]) => left - right);
  if (preparedValues.length < 2) return null;

  const [startDay, openingValue] = preparedValues[0];
  const [endDay, terminalValue] = preparedValues[preparedValues.length - 1];
  if (startDay >= endDay || openingValue <= 0 || terminalValue <= 0) return null;

  const capitalByDay = new Map<number, number>();
  for (const point of capitalHistory) {
    const day = utcDay(point.date);
    if (day != null && Number.isFinite(point.investit)) {
      capitalByDay.set(day, point.investit);
    }
  }
  const preparedCapital = [...capitalByDay.entries()].sort(([left], [right]) => left - right);
  const openingCapital = preparedCapital.filter(([day]) => day <= startDay).at(-1);
  if (!openingCapital) return null;

  let previousInvested = openingCapital[1];
  const cashFlows: CashFlow[] = [{ day: startDay, amount: -openingValue }];
  for (const [day, invested] of preparedCapital) {
    if (day <= startDay) continue;
    if (day > endDay) break;

    const contribution = invested - previousInvested;
    if (Math.abs(contribution) >= 0.005) cashFlows.push({ day, amount: -contribution });
    previousInvested = invested;
  }
  cashFlows.push({ day: endDay, amount: terminalValue });

  const rate = solveXirr(cashFlows);
  const percentage = rate == null ? null : rate * 100;
  return percentage != null && Number.isFinite(percentage) ? percentage : null;
}

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
