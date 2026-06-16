import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  activateTemplate,
  fetchEnergyBudget,
  fetchSnapshot,
  fetchSnapshots,
  fetchTemplates,
  fetchVacationMode,
  fetchWellbeing,
  setVacationMode,
} from '@/lib/snapshot'

export const snapshotKeys = {
  all: ['snapshot'] as const,
  list: (days?: number) => ['snapshot', 'list', days] as const,
  day: (date: string) => ['snapshot', 'day', date] as const,
  wellbeing: (date?: string) => ['snapshot', 'wellbeing', date] as const,
  templates: () => ['snapshot', 'templates'] as const,
  vacances: () => ['snapshot', 'vacances'] as const,
}

export const useSnapshots = (days = 30) =>
  useQuery({ queryKey: snapshotKeys.list(days), queryFn: () => fetchSnapshots(days) })

export const useSnapshot = (date: string) =>
  useQuery({ queryKey: snapshotKeys.day(date), queryFn: () => fetchSnapshot(date) })

export const useWellbeing = (date?: string) =>
  useQuery({ queryKey: snapshotKeys.wellbeing(date), queryFn: () => fetchWellbeing(date) })

export const useEnergyBudget = () =>
  useQuery({ queryKey: ['snapshot', 'energy'], queryFn: fetchEnergyBudget })

export const useTemplates = () =>
  useQuery({ queryKey: snapshotKeys.templates(), queryFn: fetchTemplates })

export const useActivateTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => activateTemplate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['routines'] }),
  })
}

export const useVacationMode = () =>
  useQuery({ queryKey: snapshotKeys.vacances(), queryFn: fetchVacationMode })

export const useSetVacationMode = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) => setVacationMode(enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: snapshotKeys.vacances() }),
  })
}
