import {apiGet} from './client';
import type {DashboardStats} from '../types';

export const analyticsApi = {
    getDashboardStats: () =>
        apiGet<DashboardStats>('/analytics/dashboard'),

    getTrends: (period: 'daily' | 'weekly' | 'monthly', months: number) =>
        apiGet<Array<{
            period: string;
            income: number;
            expenses: number;
            transaction_count: number;
        }>>('/analytics/trends', {period, months}),
};