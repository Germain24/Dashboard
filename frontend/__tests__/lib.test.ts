import { describe, it, expect } from 'vitest'
import { formatAmount, formatPercent, cn } from '@/lib/utils'
import { t } from '@/lib/i18n'
import { moduleForSlug, MODULES } from '@/lib/modules'

describe('utils', () => {
  it('formatPercent', () => {
    expect(formatPercent(42)).toBe('42%')
    expect(formatPercent(42.345, 1)).toBe('42.3%')
  })
  it('formatAmount inclut le symbole et le montant', () => {
    const s = formatAmount(1234.5)
    expect(s).toContain('1')
    expect(s).toContain('234')
  })
  it('cn fusionne et dédoublonne les classes', () => {
    expect(cn('p-2', 'p-4')).toBe('p-4') // tailwind-merge garde la dernière
    const skip: string | false = false
    expect(cn('a', skip, 'c')).toBe('a c')
  })
})

describe('i18n.t', () => {
  it('renvoie la clé si absente', () => {
    expect(t('cle.inexistante.xyz')).toBe('cle.inexistante.xyz')
  })
  it('interpole les variables', () => {
    expect(t('{n} items', { n: 3 })).toBe('3 items')
  })
})

describe('modules', () => {
  it('moduleForSlug retrouve un module connu', () => {
    expect(moduleForSlug('budget')?.label).toBe('Budget')
    expect(moduleForSlug('donnees')?.label).toBe('Données')
  })
  it('moduleForSlug renvoie undefined si inconnu', () => {
    expect(moduleForSlug('nimporte')).toBeUndefined()
  })
  it('tous les modules ont un slug et un label', () => {
    for (const m of MODULES) {
      expect(m.slug).toBeTruthy()
      expect(m.label).toBeTruthy()
    }
  })
})
