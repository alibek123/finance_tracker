// src/components/analytics/TrendChart.tsx
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from 'recharts';
import {formatMoney, formatMonth} from '../../utils/formatters';

interface TrendChartProps {
    data: Array<{
        period: string;
        income: number;
        expenses: number;
        transaction_count: number;
    }>;
    period: 'daily' | 'weekly' | 'monthly';
}

export function TrendChart({data, period}: TrendChartProps) {
    const formatXAxis = (value: string) => {
        if (period === 'monthly') {
            return formatMonth(value);
        }
        if (period === 'weekly') {
            return `Неделя ${value.split('-')[1]}`;
        }
        return new Date(value).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'short'
        });
    };

    return (
        <ResponsiveContainer width="100%" height={400}>
            <AreaChart data={data}>
                <defs>
                    <linearGradient id="colorIncome" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0.1}/>
                    </linearGradient>
                    <linearGradient id="colorExpense" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.8}/>
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0.1}/>
                    </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" className="dark:opacity-20"/>
                <XAxis
                    dataKey="period"
                    tickFormatter={formatXAxis}
                    className="text-xs"
                    tick={{fill: 'currentColor'}}
                />
                <YAxis
                    className="text-xs"
                    tick={{fill: 'currentColor'}}
                    tickFormatter={(value) => `${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip
                    contentStyle={{
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        border: '1px solid #e5e7eb',
                        borderRadius: '8px',
                    }}
                    labelFormatter={formatXAxis}
                    formatter={(value: number) => formatMoney(value)}
                />
                <Legend/>
                <Area
                    type="monotone"
                    dataKey="income"
                    stroke="#10b981"
                    fillOpacity={1}
                    fill="url(#colorIncome)"
                    name="Доходы"
                    strokeWidth={2}
                />
                <Area
                    type="monotone"
                    dataKey="expenses"
                    stroke="#ef4444"
                    fillOpacity={1}
                    fill="url(#colorExpense)"
                    name="Расходы"
                    strokeWidth={2}
                />
            </AreaChart>
        </ResponsiveContainer>
    );
}