import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { accountApi, type AccountCreateData } from '../api/accounts';
import toast from 'react-hot-toast';

export function useAccounts(includeInactive = false) {
  return useQuery({
    queryKey: ['accounts', { includeInactive }],
    queryFn: () => accountApi.getAll(includeInactive),
  });
}

export function useCreateAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: AccountCreateData) => accountApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      toast.success('Счет создан');
    },
  });
}

export function useAdjustBalance() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, newBalance, description }: {
      id: number;
      newBalance: number;
      description?: string;
    }) => accountApi.adjustBalance(id, newBalance, description),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['transactions'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });

      if (data.difference !== 0) {
        const changeType = data.difference > 0 ? 'увеличен' : 'уменьшен';
        toast.success(`Баланс ${changeType} на ${Math.abs(data.difference)} ₸`);
      }
    },
  });
}