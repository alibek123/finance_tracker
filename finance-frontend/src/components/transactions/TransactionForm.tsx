// src/components/transactions/TransactionForm.tsx
import {useForm, Controller} from 'react-hook-form';
import {zodResolver} from '@hookform/resolvers/zod';
import {z} from 'zod';
import {X} from 'lucide-react';
import {useAccounts} from '../../hooks/useAccounts';
import {useCategories} from '../../hooks/useCategories';
import {useTags} from '../../hooks/useTags';
import {useCreateTransaction} from '../../hooks/useTransactions';
import {useAppStore} from '../../store/useAppStore';
import Select from 'react-select';

// Схема валидации
const transactionSchema = z.object({
    type: z.enum(['expense', 'income', 'transfer']),
    amount: z.number().positive('Сумма должна быть положительной'),
    date: z.string().min(1, 'Выберите дату'),
    description: z.string().optional(),
    account_from_id: z.number().optional(),
    account_to_id: z.number().optional(),
    category_id: z.number().optional(),
    tag_ids: z.array(z.number()).optional(),
}).refine((data) => {
    if (data.type === 'expense') {
        return !!data.account_from_id && !!data.category_id;
    }
    if (data.type === 'income') {
        return !!data.account_to_id && !!data.category_id;
    }
    if (data.type === 'transfer') {
        return !!data.account_from_id && !!data.account_to_id;
    }
    return false;
}, {
    message: 'Заполните все обязательные поля',
    path: ['type'],
});

type TransactionFormData = z.infer<typeof transactionSchema>;

interface TransactionFormProps {
    onClose: () => void;
    onSuccess?: () => void;
}

export function TransactionForm({onClose, onSuccess}: TransactionFormProps) {
    const selectedDate = useAppStore((state) => state.selectedDate);
    const {data: accounts} = useAccounts();
    const {data: categories} = useCategories();
    const {data: tags} = useTags();
    const createTransaction = useCreateTransaction();

    const {
        register,
        control,
        handleSubmit,
        watch,
        formState: {errors},
        reset,
    } = useForm<TransactionFormData>({
        resolver: zodResolver(transactionSchema),
        defaultValues: {
            type: 'expense',
            date: selectedDate,
            tag_ids: [],
        },
    });

    const transactionType = watch('type');

    // Фильтруем категории по типу транзакции
    const filteredCategories = categories?.filter(
        (cat: { type: string; }) => cat.type === transactionType
    );

    const onSubmit = async (data: TransactionFormData) => {
        try {
            await createTransaction.mutateAsync({
                transaction_type: data.type,
                amount: data.amount,
                date: data.date,
                description: data.description,
                account_from_id: data.account_from_id,
                account_to_id: data.account_to_id,
                category_id: data.category_id,
                tag_ids: data.tag_ids,
            });
            reset();
            onSuccess?.();
            onClose();
        } catch (error) {
            // Ошибка обрабатывается в хуке
        }
    };

    return (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center p-4 z-50">
            <div className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full max-h-[90vh] overflow-y-auto">
                <div
                    className="sticky top-0 bg-white dark:bg-gray-800 border-b dark:border-gray-700 px-6 py-4 flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        Новая транзакция
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-gray-500 dark:hover:text-gray-300"
                    >
                        <X size={24}/>
                    </button>
                </div>

                <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-4">
                    {/* Тип транзакции */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                            Тип операции
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                            <label className="relative">
                                <input
                                    type="radio"
                                    value="expense"
                                    {...register('type')}
                                    className="sr-only peer"
                                />
                                <div
                                    className="text-center py-2 px-3 border rounded-lg cursor-pointer peer-checked:bg-red-100 peer-checked:border-red-500 peer-checked:text-red-700 dark:peer-checked:bg-red-900 dark:peer-checked:text-red-200 hover:bg-gray-50 dark:hover:bg-gray-700">
                                    Расход
                                </div>
                            </label>
                            <label className="relative">
                                <input
                                    type="radio"
                                    value="income"
                                    {...register('type')}
                                    className="sr-only peer"
                                />
                                <div
                                    className="text-center py-2 px-3 border rounded-lg cursor-pointer peer-checked:bg-green-100 peer-checked:border-green-500 peer-checked:text-green-700 dark:peer-checked:bg-green-900 dark:peer-checked:text-green-200 hover:bg-gray-50 dark:hover:bg-gray-700">
                                    Доход
                                </div>
                            </label>
                            <label className="relative">
                                <input
                                    type="radio"
                                    value="transfer"
                                    {...register('type')}
                                    className="sr-only peer"
                                />
                                <div
                                    className="text-center py-2 px-3 border rounded-lg cursor-pointer peer-checked:bg-blue-100 peer-checked:border-blue-500 peer-checked:text-blue-700 dark:peer-checked:bg-blue-900 dark:peer-checked:text-blue-200 hover:bg-gray-50 dark:hover:bg-gray-700">
                                    Перевод
                                </div>
                            </label>
                        </div>
                    </div>

                    {/* Сумма */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Сумма
                        </label>
                        <input
                            type="number"
                            step="0.01"
                            {...register('amount', {valueAsNumber: true})}
                            className="input"
                            placeholder="0"
                        />
                        {errors.amount && (
                            <p className="mt-1 text-sm text-red-600">{errors.amount.message}</p>
                        )}
                    </div>

                    {/* Счет списания (для расхода и перевода) */}
                    {(transactionType === 'expense' || transactionType === 'transfer') && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                {transactionType === 'expense' ? 'Счет' : 'Со счета'}
                            </label>
                            <Controller
                                name="account_from_id"
                                control={control}
                                render={({field}) => (
                                    <Select
                                        {...field}
                                        options={accounts?.map(acc => ({
                                            value: acc.id,
                                            label: `${acc.icon || '💳'} ${acc.name} (${acc.current_balance.toLocaleString()} ₸)`,
                                        }))}
                                        onChange={(option) => field.onChange(option?.value)}
                                        value={accounts?.find(acc => acc.id === field.value) ? {
                                            value: field.value,
                                            label: accounts.find(acc => acc.id === field.value)!.name,
                                        } : null}
                                        placeholder="Выберите счет"
                                        className="react-select-container"
                                        classNamePrefix="react-select"
                                        theme={(theme) => ({
                                            ...theme,
                                            colors: {
                                                ...theme.colors,
                                                primary: '#3b82f6',
                                            },
                                        })}
                                    />
                                )}
                            />
                        </div>
                    )}

                    {/* Счет зачисления (для дохода и перевода) */}
                    {(transactionType === 'income' || transactionType === 'transfer') && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                {transactionType === 'income' ? 'Счет' : 'На счет'}
                            </label>
                            <Controller
                                name="account_to_id"
                                control={control}
                                render={({field}) => (
                                    <Select
                                        {...field}
                                        options={accounts?.map(acc => ({
                                            value: acc.id,
                                            label: `${acc.icon || '💳'} ${acc.name} (${acc.current_balance.toLocaleString()} ₸)`,
                                        }))}
                                        onChange={(option) => field.onChange(option?.value)}
                                        value={accounts?.find(acc => acc.id === field.value) ? {
                                            value: field.value,
                                            label: accounts.find(acc => acc.id === field.value)!.name,
                                        } : null}
                                        placeholder="Выберите счет"
                                        className="react-select-container"
                                        classNamePrefix="react-select"
                                    />
                                )}
                            />
                        </div>
                    )}

                    {/* Категория (для доходов и расходов) */}
                    {transactionType !== 'transfer' && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                Категория
                            </label>
                            <Controller
                                name="category_id"
                                control={control}
                                render={({field}) => (
                                    <Select
                                        {...field}
                                        options={filteredCategories?.map(cat => ({
                                            value: cat.id,
                                            label: `${cat.icon || '📁'} ${cat.name}`,
                                        }))}
                                        onChange={(option) => field.onChange(option?.value)}
                                        value={filteredCategories?.find(cat => cat.id === field.value) ? {
                                            value: field.value,
                                            label: filteredCategories.find(cat => cat.id === field.value)!.name,
                                        } : null}
                                        placeholder="Выберите категорию"
                                        className="react-select-container"
                                        classNamePrefix="react-select"
                                    />
                                )}
                            />
                        </div>
                    )}

                    {/* Описание */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Описание (необязательно)
                        </label>
                        <input
                            type="text"
                            {...register('description')}
                            className="input"
                            placeholder="Например: Обед в кафе"
                        />
                    </div>

                    {/* Теги */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Теги
                        </label>
                        <Controller
                            name="tag_ids"
                            control={control}
                            render={({field}) => (
                                <Select
                                    {...field}
                                    isMulti
                                    options={tags?.map(tag => ({
                                        value: tag.id,
                                        label: tag.name,
                                    }))}
                                    onChange={(options) => field.onChange(options.map(opt => opt.value))}
                                    value={tags?.filter(tag => field.value?.includes(tag.id)).map(tag => ({
                                        value: tag.id,
                                        label: tag.name,
                                    }))}
                                    placeholder="Выберите теги"
                                    className="react-select-container"
                                    classNamePrefix="react-select"
                                />
                            )}
                        />
                    </div>

                    {/* Дата */}
                    <div>
                        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                            Дата
                        </label>
                        <input
                            type="date"
                            {...register('date')}
                            className="input"
                        />
                        {errors.date && (
                            <p className="mt-1 text-sm text-red-600">{errors.date.message}</p>
                        )}
                    </div>

                    {/* Кнопки */}
                    <div className="flex justify-end space-x-3 pt-4">
                        <button
                            type="button"
                            onClick={onClose}
                            className="btn btn-secondary"
                        >
                            Отмена
                        </button>
                        <button
                            type="submit"
                            disabled={createTransaction.isPending}
                            className="btn btn-primary"
                        >
                            {createTransaction.isPending ? 'Сохранение...' : 'Сохранить'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}