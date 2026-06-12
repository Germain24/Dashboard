import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  createDocument,
  deleteDocument,
  fetchDocuments,
  fetchEcheances,
  updateDocument,
  type Document,
  type DocType,
} from '@/lib/documents'

export const documentsKeys = {
  all: ['documents'] as const,
  list: (opts?: { type?: DocType; q?: string }) => ['documents', 'list', opts] as const,
  echeances: (days?: number) => ['documents', 'echeances', days] as const,
}

export const useDocuments = (opts?: { type?: DocType; q?: string }) =>
  useQuery({
    queryKey: documentsKeys.list(opts),
    queryFn: () => fetchDocuments(opts),
  })

export const useEcheances = (days = 90) =>
  useQuery({
    queryKey: documentsKeys.echeances(days),
    queryFn: () => fetchEcheances(days),
  })

export const useAddDocument = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<Document> & { titre: string }) => createDocument(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentsKeys.all }),
  })
}

export const useUpdateDocument = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<Document> }) =>
      updateDocument(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentsKeys.all }),
  })
}

export const useDeleteDocument = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => deleteDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentsKeys.all }),
  })
}
