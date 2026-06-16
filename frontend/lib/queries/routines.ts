import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createRoutine,
  deleteRoutine,
  applyDeepWork,
  fetchAutomationSuggestions,
  fetchBuilderOptions,
  fetchCorrelations,
  fetchWeeklyInsights,
  fetchKillSwitch,
  fetchRecipes,
  fetchRoutineRuns,
  fetchRoutines,
  rerunRoutineRun,
  rollbackRoutineRun,
  runRecipe,
  runRoutine,
  setKillSwitch,
  updateRoutine,
  type Routine,
} from '@/lib/routines'

export const routinesKeys = {
  all: ['routines'] as const,
  list: () => ['routines', 'list'] as const,
  killSwitch: () => ['routines', 'kill-switch'] as const,
  runs: () => ['routines', 'runs'] as const,
}

export const useRoutines = () =>
  useQuery({ queryKey: routinesKeys.list(), queryFn: fetchRoutines })

export const useAddRoutine = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Routine> & { name: string }) => createRoutine(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.all }),
  })
}

export const useUpdateRoutine = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Routine> }) =>
      updateRoutine(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.all }),
  })
}

export const useDeleteRoutine = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteRoutine(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.all }),
  })
}

export const useRunRoutine = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => runRoutine(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.runs() }),
  })
}

export const useKillSwitch = () =>
  useQuery({ queryKey: routinesKeys.killSwitch(), queryFn: fetchKillSwitch })

export const useSetKillSwitch = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) => setKillSwitch(enabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.killSwitch() }),
  })
}

export const useRoutineRuns = (limit = 30) =>
  useQuery({ queryKey: routinesKeys.runs(), queryFn: () => fetchRoutineRuns(limit) })

// Ré-exécution + rollback d'un run (#216)
export const useRerunRun = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (runId: number) => rerunRoutineRun(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.all }),
  })
}

export const useRollbackRun = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (runId: number) => rollbackRoutineRun(runId),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.runs() }),
  })
}

export const useWeeklyInsights = () =>
  useQuery({ queryKey: ['routines', 'insights'], queryFn: fetchWeeklyInsights })

export const useCorrelations = () =>
  useQuery({ queryKey: ['routines', 'correlations'], queryFn: fetchCorrelations })

export const useApplyDeepWork = () =>
  useMutation({ mutationFn: (nBlocks?: number) => applyDeepWork(nBlocks) })

export const useAutomationSuggestions = () =>
  useQuery({ queryKey: ['routines', 'suggestions'], queryFn: fetchAutomationSuggestions })

export const useBuilderOptions = () =>
  useQuery({ queryKey: ['routines', 'builder-options'], queryFn: fetchBuilderOptions, staleTime: Infinity })

export const useRecipes = () =>
  useQuery({ queryKey: ['routines', 'recipes'], queryFn: fetchRecipes, staleTime: Infinity })

export const useRunRecipe = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => runRecipe(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: routinesKeys.runs() }),
  })
}
