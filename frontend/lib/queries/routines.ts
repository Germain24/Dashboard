import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createRoutine,
  deleteRoutine,
  fetchRoutines,
  runRoutine,
  updateRoutine,
  type Routine,
} from '@/lib/routines'

export const routinesKeys = {
  all: ['routines'] as const,
  list: () => ['routines', 'list'] as const,
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

export const useRunRoutine = () =>
  useMutation({ mutationFn: (id: number) => runRoutine(id) })
