import {Trash2} from 'lucide-react';
import type {Transaction} from '../../types';
import {formatMoney, formatDate} from '../../utils/formatters';
import clsx from 'clsx';

interface TransactionItemProps {
    transaction: Transaction;
    onDelete?: (id: number) => void;
    showActions?: boolean;
}

export function TransactionItem({
                                    transaction,
                                    onDelete,
                                    showActions = false
                                }: TransactionItemProps) {
    const getAmountColor = (type: string) => {
        switch (type) {
            case 'income':
                return 'text-green-600';
            case 'expense':
                return 'text-red-600';
            case 'transfer':
                return 'text-blue-600';
            default:
                return 'text-gray-600';
        }
    };

    const getAccountName = (t: Transaction) => {
        if (t.type === 'expense') return t.account_from_name;
        if (t.type === 'income') return t.account_to_name;
        if (t.type === 'transfer') return `${t.account_from_name} → ${t.account_to_name}`;
        return '';
    };

    return (
        <div
            className="flex items-center justify-between py-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 px-2 rounded-lg transition-colors">
            <div className="flex items-center space-x-4">
                <div
                    className="w-12 h-12 rounded-lg flex items-center justify-center text-xl flex-shrink-0"
                    style={{
                        backgroundColor: `${transaction.category_color}20`,
                        color: transaction.category_color
                    }}
                >
                    {transaction.category_icon || '📝'}
                </div>
                <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                        {transaction.description || transaction.category_name}
                    </p>
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                        {formatDate(transaction.date)} • {getAccountName(transaction)}
                    </p>
                    {transaction.tags && transaction.tags.length > 0 && (
                        <div className="flex gap-1 mt-1">
                            {transaction.tags.map((tag, index) => (
                                <span
                                    key={index}
                                    className="inline-block px-2 py-1 text-xs bg-gray-200 dark:bg-gray-700 rounded-full"
                                >
                  {tag}
                </span>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            <div className="flex items-center space-x-3">
                <p className={clsx('font-semibold', getAmountColor(transaction.type))}>
                    {transaction.type === 'expense' ? '-' : '+'} {formatMoney(transaction.amount)}
                </p>
                {showActions && onDelete && (
                    <button
                        onClick={() => onDelete(transaction.id)}
                        className="p-1 text-gray-400 hover:text-red-600 transition-colors"
                    >
                        <Trash2 size={18}/>
                    </button>
                )}
            </div>
        </div>
    );
}