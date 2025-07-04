import axios, {AxiosError, type AxiosRequestConfig} from 'axios';
import {notifyError} from '../utils/notify';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const apiClient = axios.create({
    baseURL: API_URL,
    headers: {'Content-Type': 'application/json'},
    withCredentials: true,
    timeout: 10_000,
});

// Интерсептор для обработки ошибок
apiClient.interceptors.response.use(
    response => response,
    (error: AxiosError) => {
        const data = error.response?.data as any;
        const message: string =
            typeof data?.detail === 'string'
                ? data.detail
                : Array.isArray(data?.detail)
                    ? data.detail.join('\n')
                    : data?.message || 'Произошла ошибка';

        if (error.response?.status !== 401) {
            notifyError(message);
        }

        console.error('API error', {
            url: error.config?.url,
            status: error.response?.status,
            data: error.response?.data,
        });

        return Promise.reject(error);
    }
);

export async function apiGet<T, P extends object = object>(
    url: string,
    params?: P
): Promise<T> {
    const response = await apiClient.get<T>(url, {params});
    return response.data;
}

export async function apiPost<T>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
): Promise<T> {
    const response = await apiClient.post<T>(url, data, config);
    return response.data;
}

export async function apiPut<T>(
    url: string,
    data?: unknown,
    config?: AxiosRequestConfig
): Promise<T> {
    const response = await apiClient.put<T>(url, data, config);
    return response.data;
}

export async function apiDelete<T>(
    url: string,
    config?: AxiosRequestConfig
): Promise<T> {
    const response = await apiClient.delete<T>(url, config);
    return response.data;
}
