import { describe, it, expect } from 'vitest'
import { securityHeaders } from '@/lib/securityHeaders'

describe('securityHeaders (#194)', () => {
  const byKey = (k: string) =>
    securityHeaders.find((h) => h.key.toLowerCase() === k.toLowerCase())?.value ?? ''

  it('protège du clickjacking', () => {
    expect(byKey('X-Frame-Options')).toBe('DENY')
    expect(byKey('Content-Security-Policy')).toContain("frame-ancestors 'none'")
  })

  it('empêche le MIME-sniffing', () => {
    expect(byKey('X-Content-Type-Options')).toBe('nosniff')
  })

  it('limite la fuite de referrer', () => {
    expect(byKey('Referrer-Policy')).toBeTruthy()
  })

  it('définit une CSP avec default-src self', () => {
    const csp = byKey('Content-Security-Policy')
    expect(csp).toContain("default-src 'self'")
  })
})
