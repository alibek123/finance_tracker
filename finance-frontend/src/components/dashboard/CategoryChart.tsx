// src/components/dashboard/CategoryChart.tsx
import {
    PieChart,
    Pie,
    Cell,
    ResponsiveContainer,
    Legend,
    Tooltip,
} from 'recharts';
import {formatMoney} from '../../utils/formatters';

interface CategoryChartProps {
    data: Array<{
        category_name: string;
        amount: number;
        color?: string;
        icon?: string;
    }>;
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export function CategoryChart({data}: CategoryChartProps) {
    const chartData = data.map((item, index) => ({
        name: item.category_name,
        value: item.amount,
        color: item.color || COLORS[index % COLORS.length],
        icon: item.icon,
    }));

    const CustomTooltip = ({active, payload}: any) => {
        if (active && payload && payload.length) {
            const data = payload[0];
            return (
                <div className="bg-white dark:bg-gray-800 p-3 rounded-lg shadow-lg border dark:border-gray-700">
                    <p className="font-medium flex items-center gap-2">
                        <span>{data.payload.icon}</span>
                        {data.name}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">
                        {formatMoney(data.value)}
                    </p>
                </div>
            );
        }
        return null;
    };

    const renderCustomLabel = ({cx, cy, midAngle, innerRadius, outerRadius, percent}: any) => {
        const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
        const x = cx + radius * Math.cos(-midAngle * Math.PI / 180);
        const y = cy + radius * Math.sin(-midAngle * Math.PI / 180);

        if (percent < 0.05) return null; // Не показываем метки для маленьких секторов

        return (
            <text
                x={x}
                y={y}
                fill="white"
                textAnchor={x > cx ? 'start' : 'end'}
                dominantBaseline="central"
                className="text-xs font-medium"
            >
                {`${(percent * 100).toFixed(0)}%`}
            </text>
        );
    };

    return (
        <ResponsiveContainer width="100%" height={300}>
            <PieChart>
                <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={renderCustomLabel}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                >
                    {chartData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color}/>
                    ))}
                </Pie>
                <Tooltip content={<CustomTooltip/>}/>
                <Legend
                    verticalAlign="bottom"
                    height={36}
                    formatter={(value, entry: any) => (
                        <span className="text-sm">
              {entry.payload.icon} {value}
            </span>
                    )}
                />
            </PieChart>
        </ResponsiveContainer>
    );
}