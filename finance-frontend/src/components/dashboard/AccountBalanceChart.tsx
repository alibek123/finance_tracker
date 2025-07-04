// src/components/analytics/AccountBalanceChart.tsx
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Cell,
} from 'recharts';
import {formatMoney} from '../../utils/formatters';
import type {Account} from '../../types';

interface AccountBalanceChartProps {
    accounts: Account[];
}

export function AccountBalanceChart({accounts}: AccountBalanceChartProps) {
    const chartData = accounts.map(account => ({
        name: account.name,
        balance: account.current_balance,
        color: account.color || '#3b82f6',
        icon: account.icon,
    }));

    const CustomTooltip = ({active, payload}: any) => {
        if (active && payload && payload.length) {
            const data = payload[0];
            return (
                <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-lg border dark:border-gray-700">
                    <p className="font-medium flex items-center gap-2">
                        <span>{data.payload.icon}</span>
                        {data.payload.name}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                        {formatMoney(data.value)}
                    </p>
                </div>
            );
        }
        return null;
    };

    return (
        <ResponsiveContainer width="100%" height={300}>
            <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="dark:opacity-20"/>
                <XAxis
                    dataKey="name"
                    className="text-xs"
                    tick={{fill: 'currentColor'}}
                />
                <YAxis
                    className="text-xs"
                    tick={{fill: 'currentColor'}}
                    tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip content={<CustomTooltip/>}/>
                <Bar dataKey="balance" radius={[8, 8, 0, 0]}>
                    {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color}/>
                    ))}
                </Bar>
            </BarChart>
        </ResponsiveContainer>
    );
}