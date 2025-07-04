import type {LucideIcon} from 'lucide-react';
import {formatMoney} from '../../utils/formatters';

interface StatsCardProps {
    title: string;
    value: number;
    icon: LucideIcon;
    color: 'blue' | 'green' | 'red' | 'purple';
    currency?: string;
}

export function StatsCard({title, value, icon: Icon, color, currency = '₸'}: StatsCardProps) {
    const colorClasses = {
        blue: 'bg-blue-500',
        green: 'bg-green-500',
        red: 'bg-red-500',
        purple: 'bg-purple-500',
    };

    return (
        <div className="card p-6">
            <div className="flex items-center justify-between">
                <div className="flex-1">
                    <p className="text-sm font-medium text-gray-600 dark:text-gray-400">
                        {title}
                    </p>
                    <p className="mt-2 text-2xl font-bold text-gray-900 dark:text-white">
                        {formatMoney(value, currency)}
                    </p>
                </div>
                <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
                    <Icon className="h-6 w-6 text-white"/>
                </div>
            </div>
        </div>
    );
}