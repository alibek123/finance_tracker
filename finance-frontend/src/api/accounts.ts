import {apiGet, apiPost, apiPut, apiDelete} from './client';
import type {Account} from '../types';

export interface AccountCreateData {
    name: string;
    account_type: Account['type'];
    initial_balance: number;
    currency?: string;
    icon?: string;
    color?: string;
}

export const accountApi = {
    getAll: (include_inactive = false) =>
        apiGet<Account[]>('/accounts', {include_inactive}),

    create: (data: AccountCreateData) =>
        apiPost<Account>('/accounts', data),

    update: (id: number, data: Partial<AccountCreateData>) =>
        apiPut<Account>(`/accounts/${id}`, data),

    delete: (id: number) =>
        apiDelete<{ message: string }>(`/accounts/${id}`),

    adjustBalance: (id: number, newBalance: number, description?: string) =>
        apiPost<{ message: string; old_balance: number; new_balance: number; difference: number }>(
            `/accounts/${id}/adjust-balance`,
            null,
            {params: {new_balance: newBalance, description}}
        ),
};