interface LoadingSpinnerProps {
    size?: 'sm' | 'md' | 'lg';
    centered?: boolean;
}

export function LoadingSpinner({size = 'md', centered = true}: LoadingSpinnerProps) {
    const sizeClasses = {
        sm: 'h-4 w-4 border-2',
        md: 'h-8 w-8 border-3',
        lg: 'h-12 w-12 border-4',
    };

    const spinner = (
        <div className={`animate-spin rounded-full border-primary-600 border-t-transparent ${sizeClasses[size]}`}/>
    );

    if (centered) {
        return (
            <div className="flex items-center justify-center p-8">
                {spinner}
            </div>
        );
    }

    return spinner;
}