import {useQuery} from '@tanstack/react-query';
import {Wallet, TrendingUp, TrendingDown, PiggyBank} from 'lucide-react';
import {analyticsApi} from '../api/analytics';
import {transactionApi} from '../api/transactions';
import {StatsCard} from '../components/dashboard/StatsCard';
import {Card, CardHeader} from '../components/common/Card';
import {LoadingSpinner} from '../components/common/LoadingSpinner';
import {TransactionList} from '../components/transactions/TransactionList';
import {ExpenseChart} from '../components/dashboard/ExpenseChart';

// import {CategoryChart} from '../components/dashboard/CategoryChart';

export function Dashboard() {
    const {data: stats, isLoading: statsLoading} = useQuery({
        queryKey: ['dashboard'],
        queryFn: analyticsApi.getDashboardStats,
    });

    const {data: recentTransactions, isLoading: transactionsLoading} = useQuery({
        queryKey: ['transactions', 'recent'],
        queryFn: () => transactionApi.getAll({limit: 5}),
    });

    if (statsLoading || transactionsLoading) {
        return <LoadingSpinner/>;
    }

    if (!stats) {
        return <div>Ошибка загрузки данных</div>;
    }

    return (
        <div className="space-y-6">
            {/* Карточки статистики */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                <StatsCard
                    title="Общий баланс"
                    value={stats.total_balance}
                    icon={Wallet}
                    color="blue"
                />
                <StatsCard
                    title="Доходы за месяц"
                    value={stats.total_income}
                    icon={TrendingUp}
                    color="green"
                />
                <StatsCard
                    title="Расходы за месяц"
                    value={stats.total_expense}
                    icon={TrendingDown}
                    color="red"
                />
                <StatsCard
                    title="Сбережения"
                    value={stats.net_savings}
                    icon={PiggyBank}
                    color="purple"
                />
            </div>

            {/* Графики */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-2">
                    <Card>
                        <CardHeader>Расходы за последние 30 дней</CardHeader>
                        <ExpenseChart data={stats.daily_expenses}/>
                    </Card>
                </div>
                <div>
                    <Card>
                        <CardHeader>Топ категорий</CardHeader>
                        {/*<CategoryChart data={stats.category_breakdown}/>*/}
                    </Card>
                </div>
            </div>

            {/* Последние транзакции */}
            <Card>
                <CardHeader>Последние транзакции</CardHeader>
                {recentTransactions && recentTransactions.length > 0 ? (
                    <TransactionList transactions={recentTransactions}/>
                ) : (
                    <p className="text-gray-500 text-center py-8">Нет транзакций</p>
                )}
            </Card>
        </div>
    );
}