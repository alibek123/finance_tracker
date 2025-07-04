import type {Transaction} from '../../types';
import {TransactionItem} from './TransactionItem';

interface TransactionListProps {
    transactions: Transaction[];
    onDelete?: (id: number) => void;
    showActions?: boolean;
}

export function TransactionList({
                                    transactions,
                                    onDelete,
                                    showActions = false
                                }: TransactionListProps) {
    if (transactions.length === 0) {
        return (
            <p className="text-center text-gray-500 dark:text-gray-400 py-8">
                Нет транзакций
            </p>
        );
    }

    return (
        <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {transactions.map((transaction) => (
                <TransactionItem
                    key={transaction.id}
                    transaction={transaction}
                    onDelete={onDelete}
                    showActions={showActions}
                />
            ))}
        </div>
    );
}