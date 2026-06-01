'use client'
import { useState } from 'react'
import { Library } from 'lucide-react'
import BibliothequeTab from '@/components/livres/BibliothequeTab'

const TABS = [{ id: 'bibliotheque', label: 'Bibliothèque', icon: Library }]

export default function LivresPage() {
  const [active, setActive] = useState('bibliotheque')
  return (
    <div className="space-y-0 animate-fade-in">
      <div className="px-6 py-5 border-b border-[var(--border)]">
        <div className="mb-4">
          <h1 className="text-xl font-semibold tracking-tight">Livres</h1>
          <p className="text-sm text-[var(--muted-foreground)] mt-0.5">Bibliothèque personnelle</p>
        </div>
        <div className="flex gap-1">
          {TABS.map(tab => {
            const Icon = tab.icon
            return (
              <button key={tab.id} onClick={() => setActive(tab.id)}
                className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-md transition-all duration-200 cursor-pointer text-[var(--ring)] bg-[color-mix(in_srgb,var(--ring)_10%,transparent)]">
                <Icon size={15} />{tab.label}
              </button>
            )
          })}
        </div>
      </div>
      <div className="p-6 animate-fade-in-up">
        <BibliothequeTab />
      </div>
    </div>
  )
}
