// src/pages/Transactions.tsx
import React, {useState, useCallback, useMemo} from 'react';
import {Plus, Search, Filter, Download, Upload} from 'lucide-react';
import {useSearchTransactions, useDeleteTransaction} from '../hooks/useTransactions';
import {useAccounts} from '../hooks/useAccounts';
// import {useCategories} from '../hooks/useCategories';
// import {useTags} from '../hooks/useTags';
import {Card, CardHeader} from '../components/common/Card';
import {LoadingSpinner} from '../components/common/LoadingSpinner';
import {TransactionList} from '../components/transactions/TransactionList';
import {TransactionForm} from '../components/transactions/TransactionForm';
import type {TransactionFilters} from '../api/transactions';
import Select from 'react-select';
import {formatDate} from '../utils/formatters';
import {useDebounce} from '../hooks/useDebounce';

export function Transactions() {
    const [showForm, setShowForm] = useState(false);
    const [showFilters, setShowFilters] = useState(false);
    const [searchQuery, setSearchQuery] = useState('');
    const [filters, setFilters] = useState<TransactionFilters>({
        limit: 50,
        offset: 0,
    });

    // Дебаунс для поиска
    const debouncedSearch = useDebounce(searchQuery, 300);

    // Запрос с фильтрами
    const searchFilters = useMemo(() => ({
        ...filters,
        q: debouncedSearch || undefined,
    }), [filters, debouncedSearch]);

    const {data, isLoading, refetch} = useSearchTransactions(searchFilters);
    const deleteTransaction = useDeleteTransaction();
    const {data: accounts} = useAccounts();
    // const {data: categories} = useCategories();
    // const {data: tags} = useTags();

    const handleDelete = useCallback(async (id: number) => {
        if (window.confirm('Вы уверены, что хотите удалить эту транзакцию?')) {
            await deleteTransaction.mutateAsync(id);
        }
    }, [deleteTransaction]);

    const handleFilterChange = (key: keyof TransactionFilters, value: any) => {
        setFilters(prev => ({
            ...prev,
            [key]: value,
            offset: 0, // Сбрасываем пагинацию при изменении фильтров
        }));
    };

    const handleExport = async (format: 'csv' | 'json') => {
        const params = new URLSearchParams();
        if (filters.start_date) params.append('start_date', filters.start_date);
        if (filters.end_date) params.append('end_date', filters.end_date);

        const url = `${import.meta.env.VITE_API_URL}/data/export/${format}?${params}`;
        window.open(url, '_blank');
    };

    const handleImport = () => {
        // Здесь можно открыть модальное окно для импорта
        alert('Функция импорта будет реализована');
    };

    const handlePageChange = (newOffset: number) => {
        setFilters(prev => ({...prev, offset: newOffset}));
    };

    return (
        <div className="space-y-6">
            {/* Заголовок и действия */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    Транзакции
                </h1>
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => handleExport('csv')}
                        className="btn btn-secondary flex items-center gap-2"
                    >
                        <Download size={16}/>
                        <span className="hidden sm:inline">CSV</span>
                    </button>
                    <button
                        onClick={() => handleExport('json')}
                        className="btn btn-secondary flex items-center gap-2"
                    >
                        <Download size={16}/>
                        <span className="hidden sm:inline">JSON</span>
                    </button>
                    <button
                        onClick={handleImport}
                        className="btn btn-secondary flex items-center gap-2"
                    >
                        <Upload size={16}/>
                        <span className="hidden sm:inline">Импорт</span>
                    </button>
                    <button
                        onClick={() => setShowForm(true)}
                        className="btn btn-primary flex items-center gap-2"
                    >
                        <Plus size={20}/>
                        Добавить
                    </button>
                </div>
            </div>

            {/* Поиск и фильтры */}
            <Card>
                <div className="space-y-4">
                    {/* Строка поиска */}
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20}/>
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="Поиск по описанию, категории, счету..."
                            className="input pl-10"
                        />
                    </div>

                    {/* Кнопка фильтров */}
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className="flex items-center gap-2 text-primary-600 hover:text-primary-700"
                    >
                        <Filter size={16}/>
                        {showFilters ? 'Скрыть фильтры' : 'Показать фильтры'}
                    </button>

                    {/* Панель фильтров */}
                    {showFilters && (
                        <div
                            className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-4 border-t dark:border-gray-700">
                            {/* Даты */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Период с
                                </label>
                                <input
                                    type="date"
                                    value={filters.start_date || ''}
                                    onChange={(e) => handleFilterChange('start_date', e.target.value)}
                                    className="input"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    по
                                </label>
                                <input
                                    type="date"
                                    value={filters.end_date || ''}
                                    onChange={(e) => handleFilterChange('end_date', e.target.value)}
                                    className="input"
                                />
                            </div>

                            {/* Тип транзакции */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Тип
                                </label>
                                <Select
                                    isClearable
                                    options={[
                                        {value: 'expense', label: 'Расход'},
                                        {value: 'income', label: 'Доход'},
                                        {value: 'transfer', label: 'Перевод'},
                                    ]}
                                    onChange={(option) => handleFilterChange('transaction_types', option?.value)}
                                    placeholder="Все типы"
                                    className="react-select-container"
                                    classNamePrefix="react-select"
                                />
                            </div>

                            {/* Счета */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Счета
                                </label>
                                <Select
                                    isMulti
                                    options={accounts?.map(acc => ({
                                        value: acc.id,
                                        label: `${acc.icon || '💳'} ${acc.name}`,
                                    }))}
                                    onChange={(options) => handleFilterChange('account_ids', options.map(o => o.value).join(','))}
                                    placeholder="Все счета"
                                    className="react-select-container"
                                    classNamePrefix="react-select"
                                />
                            </div>

                            {/* Категории */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Категории
                                </label>
                                <Select
                                    isMulti
                                    // options={categories?.map(cat => ({
                                    //     value: cat.id,
                                    //     label: `${cat.icon || '📁'} ${cat.name}`,
                                    // }))}
                                    onChange={(options) => handleFilterChange('category_ids', options.map(o => o.value).join(','))}
                                    placeholder="Все категории"
                                    className="react-select-container"
                                    classNamePrefix="react-select"
                                />
                            </div>

                            {/* Теги */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Теги
                                </label>
                                <Select
                                    isMulti
                                    // options={tags?.map(tag => ({
                                    //     value: tag.id,
                                    //     label: tag.name,
                                    // }))}
                                    onChange={(options) => handleFilterChange('tag_ids', options.map(o => o.value).join(','))}
                                    placeholder="Все теги"
                                    className="react-select-container"
                                    classNamePrefix="react-select"
                                />
                            </div>

                            {/* Суммы */}
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Сумма от
                                </label>
                                <input
                                    type="number"
                                    value={filters.min_amount || ''}
                                    onChange={(e) => handleFilterChange('min_amount', e.target.value ? Number(e.target.value) : undefined)}
                                    className="input"
                                    placeholder="0"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    до
                                </label>
                                <input
                                    type="number"
                                    value={filters.max_amount || ''}
                                    onChange={(e) => handleFilterChange('max_amount', e.target.value ? Number(e.target.value) : undefined)}
                                    className="input"
                                    placeholder="999999"
                                />
                            </div>

                            {/* Кнопка сброса */}
                            <div className="flex items-end">
                                <button
                                    onClick={() => {
                                        setFilters({limit: 50, offset: 0});
                                        setSearchQuery('');
                                    }}
                                    className="btn btn-secondary w-full"
                                >
                                    Сбросить фильтры
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </Card>

            {/* Список транзакций */}
            <Card padding={false}>
                {isLoading ? (
                    <LoadingSpinner/>
                ) : (
                    <>
                        {/* Информация о результатах */}
                        {data && (
                            <div className="px-6 py-3 border-b dark:border-gray-700">
                                <p className="text-sm text-gray-600 dark:text-gray-400">
                                    Найдено транзакций: {data.total}
                                </p>
                            </div>
                        )}

                        {/* Список */}
                        <div className="px-6 py-4">
                            {data?.transactions && data.transactions.length > 0 ? (
                                <TransactionList
                                    transactions={data.transactions}
                                    onDelete={handleDelete}
                                    showActions
                                />
                            ) : (
                                <p className="text-center text-gray-500 dark:text-gray-400 py-8">
                                    Транзакции не найдены
                                </p>
                            )}
                        </div>

                        {/* Пагинация */}
                        {data && data.total > filters.limit && (
                            <div className="px-6 py-4 border-t dark:border-gray-700">
                                <div className="flex items-center justify-between">
                                    <button
                                        onClick={() => handlePageChange(Math.max(0, filters.offset - filters.limit))}
                                        disabled={filters.offset === 0}
                                        className="btn btn-secondary disabled:opacity-50"
                                    >
                                        Предыдущая
                                    </button>
                                    <span className="text-sm text-gray-600 dark:text-gray-400">
                    {filters.offset + 1} - {Math.min(filters.offset + filters.limit, data.total)} из {data.total}
                  </span>
                                    <button
                                        onClick={() => handlePageChange(filters.offset + filters.limit)}
                                        disabled={filters.offset + filters.limit >= data.total}
                                        className="btn btn-secondary disabled:opacity-50"
                                    >
                                        Следующая
                                    </button>
                                </div>
                            </div>
                        )}
                    </>
                )}
            </Card>

            {/* Форма добавления транзакции */}
            {showForm && (
                <TransactionForm
                    onClose={() => setShowForm(false)}
                    onSuccess={() => refetch()}
                />
            )}
        </div>
    );
}

