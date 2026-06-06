const BASE = '/api/budget'

export async function fetchTransactions(params?: { from?: string; to?: string; category_id?: number }) {
  const q = new URLSearchParams(params as any).toString()
  const res = await fetch(`${BASE}/transactions${q ? '?' + q : ''}`)
  return res.json()
}

export async function createTransaction(data: { date: string; montant: number; marchand: string; description?: string; compte?: string }) {
  const res = await fetch(`${BASE}/transactions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
  return res.json()
}

export async function fetchCategories() {
  return (await fetch(`${BASE}/categories`)).json()
}

export async function fetchSummary(month: string) {
  return (await fetch(`${BASE}/summary?month=${month}`)).json()
}

export async function fetchEnvelopes(month: string) {
  return (await fetch(`${BASE}/envelopes?month=${month}`)).json()
}

export async function fetchDisposable(month: string) {
  return (await fetch(`${BASE}/disposable?month=${month}`)).json()
}

export async function fetchCashflow(from: string, to: string) {
  return (await fetch(`${BASE}/cashflow?from_date=${from}&to_date=${to}`)).json()
}

export type CategorySpend = { category_id: number | null; nom: string; couleur: string; montant: number; pct: number }
export type MonthTrend = { mois: string; revenus: number; depenses: number }

export async function fetchByCategory(month: string): Promise<CategorySpend[]> {
  const d = await (await fetch(`${BASE}/by-category?month=${month}`)).json()
  return Array.isArray(d) ? d : []
}

export async function fetchTrend(months = 6): Promise<MonthTrend[]> {
  const d = await (await fetch(`${BASE}/trend?months=${months}`)).json()
  return Array.isArray(d) ? d : []
}

export async function fetchRules() {
  return (await fetch(`${BASE}/rules`)).json()
}

export async function applyRules() {
  return (await fetch(`${BASE}/rules/apply`, { method: 'POST' })).json()
}
