import {apiGet, apiPost, apiPut, apiDelete} from './client';
import type {Transaction} from '../types';

export interface TransactionFilters {
    q?: string;
    start_date?: string;
    end_date?: string;
    min_amount?: number;
    max_amount?: number;
    account_ids?: string;
    category_ids?: string;
    tag_ids?: string;
    transaction_types?: string;
    limit?: number;
    offset?: number;
}

export interface TransactionCreateData {
    transaction_type: 'expense' | 'income' | 'transfer';
    amount: number;
    date: string;
    description?: string;
    account_from_id?: number;
    account_to_id?: number;
    category_id?: number;
    tag_ids?: number[];
}

export const transactionApi = {
    // Получить список транзакций
    getAll: (filters?: TransactionFilters) =>
        apiGet<Transaction[]>('/transactions', filters),

    // Получить одну транзакцию
    getById: (id: number) =>
        apiGet<Transaction>(`/transactions/${id}`),

    // Создать транзакцию
    create: (data: TransactionCreateData) =>
        apiPost<Transaction>('/transactions', data),

    // Обновить транзакцию
    update: (id: number, data: Partial<TransactionCreateData>) =>
        apiPut<Transaction>(`/transactions/${id}`, data),

    // Удалить транзакцию
    delete: (id: number) =>
        apiDelete<{ message: string }>(`/transactions/${id}`),

    // Поиск транзакций
    search: (filters: TransactionFilters) =>
        apiGet<{
            transactions: Transaction[];
            total: number;
            limit: number;
            offset: number;
        }>('/transactions/search', filters),
};