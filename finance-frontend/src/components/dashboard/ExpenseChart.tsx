// src/components/dashboard/ExpenseChart.tsx
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
} from 'recharts';
import {format} from 'date-fns';
import {ru} from 'date-fns/locale';
import {formatMoney} from '../../utils/formatters';

interface ExpenseChartProps {
    data: Array<{
        date: string;
        amount: number;
    }>;
}

export function ExpenseChart({data}: ExpenseChartProps) {
    const chartData = data.map(item => ({
        date: format(new Date(item.date), 'd MMM', {locale: ru}),
        amount: item.amount,
    }));

    return (
        <ResponsiveContainer width="100%" height={300}>
            <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" className="dark:opacity-20"/>
                <XAxis
                    dataKey="date"
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
                    labelStyle={{color: '#111827'}}
                    formatter={(value: number) => formatMoney(value)}
                />
                <Line
                    type="monotone"
                    dataKey="amount"
                    stroke="#ef4444"
                    strokeWidth={2}
                    dot={{fill: '#ef4444', r: 4}}
                    activeDot={{r: 6}}
                />
            </LineChart>
        </ResponsiveContainer>
    );
}