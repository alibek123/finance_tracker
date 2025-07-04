import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { transactionApi, type TransactionFilters, type TransactionCreateData } from '../api/transactions';
import toast from 'react-hot-toast';

// Ключи для кеширования
const QUERY_KEYS = {
  all: ['transactions'] as const,
  lists: () => [...QUERY_KEYS.all, 'list'] as const,
  list: (filters?: TransactionFilters) => [...QUERY_KEYS.lists(), filters] as const,
  details: () => [...QUERY_KEYS.all, 'detail'] as const,
  detail: (id: number) => [...QUERY_KEYS.details(), id] as const,
};

// Хук для получения списка транзакций
export function useTransactions(filters?: TransactionFilters) {
  return useQuery({
    queryKey: QUERY_KEYS.list(filters),
    queryFn: () => transactionApi.getAll(filters),
  });
}

// Хук для получения одной транзакции
export function useTransaction(id: number) {
  return useQuery({
    queryKey: QUERY_KEYS.detail(id),
    queryFn: () => transactionApi.getById(id),
    enabled: !!id,
  });
}

// Хук для создания транзакции
export function useCreateTransaction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: TransactionCreateData) => transactionApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success('Транзакция добавлена');
    },
    onError: () => {
      toast.error('Ошибка при добавлении транзакции');
    },
  });
}

// Хук для удаления транзакции
export function useDeleteTransaction() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => transactionApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.all });
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      toast.success('Транзакция удалена');
    },
  });
}

// Хук для поиска транзакций
export function useSearchTransactions(filters: TransactionFilters) {
  return useQuery({
    queryKey: ['transactions', 'search', filters],
    queryFn: () => transactionApi.search(filters),
    enabled: !!filters.q || !!filters.start_date || !!filters.end_date,
  });
}