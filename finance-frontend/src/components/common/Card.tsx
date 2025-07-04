import React from 'react';
import clsx from 'clsx';

interface CardProps {
    children: React.ReactNode;
    className?: string;
    padding?: boolean;
}

export function Card({children, className, padding = true}: CardProps) {
    return (
        <div className={clsx('card', {'p-6': padding}, className)}>
            {children}
        </div>
    );
}

interface CardHeaderProps {
    children: React.ReactNode;
    className?: string;
    action?: React.ReactNode;
}

export function CardHeader({children, className, action}: CardHeaderProps) {
    return (
        <div className={clsx('flex items-center justify-between mb-4', className)}>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {children}
            </h3>
            {action}
        </div>
    );
}