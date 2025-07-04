import {useEffect} from 'react';
import {Outlet, NavLink} from 'react-router-dom';
import {
    LayoutDashboard,
    Receipt,
    PiggyBank,
    Target,
    BarChart3,
    Settings,
    Sun,
    Moon,
    Calendar,
    Menu,
    X
} from 'lucide-react';
import {useAppStore} from '../../store/useAppStore';
import clsx from 'clsx';

const navigation = [
    {name: 'Обзор', href: '/', icon: LayoutDashboard},
    {name: 'Транзакции', href: '/transactions', icon: Receipt},
    {name: 'Бюджеты', href: '/budgets', icon: PiggyBank},
    {name: 'Цели', href: '/goals', icon: Target},
    {name: 'Аналитика', href: '/analytics', icon: BarChart3},
    {name: 'Настройки', href: '/settings', icon: Settings},
];

export function Layout() {
    const {darkMode, toggleDarkMode, sidebarOpen, toggleSidebar, selectedDate, setSelectedDate} = useAppStore();

    useEffect(() => {
        if (darkMode) {
            document.documentElement.classList.add('dark');
        } else {
            document.documentElement.classList.remove('dark');
        }
    }, [darkMode]);

    return (
        <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
            {/* Header */}
            <header className="bg-gradient-to-r from-primary-600 to-purple-600 text-white shadow-lg sticky top-0 z-40">
                <div className="px-4 sm:px-6 lg:px-8">
                    <div className="flex items-center justify-between h-16">
                        <div className="flex items-center">
                            <button
                                onClick={toggleSidebar}
                                className="p-2 rounded-md text-white hover:bg-white/20 lg:hidden"
                            >
                                {sidebarOpen ? <X size={24}/> : <Menu size={24}/>}
                            </button>
                            <h1 className="ml-2 text-xl font-bold">Мои финансы</h1>
                        </div>

                        <div className="flex items-center space-x-4">
                            <button
                                onClick={toggleDarkMode}
                                className="p-2 rounded-lg hover:bg-white/20 transition-colors"
                            >
                                {darkMode ? <Sun size={20}/> : <Moon size={20}/>}
                            </button>

                            <div className="relative">
                                <input
                                    type="date"
                                    value={selectedDate}
                                    onChange={(e) => setSelectedDate(e.target.value)}
                                    className="appearance-none bg-white/20 hover:bg-white/30 transition-colors rounded-lg px-3 py-2 pl-10 cursor-pointer text-white"
                                    style={{colorScheme: 'dark'}}
                                />
                                <Calendar
                                    className="absolute left-3 top-1/2 transform -translate-y-1/2 pointer-events-none"
                                    size={16}/>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <div className="flex h-[calc(100vh-64px)]">
                {/* Sidebar */}
                <aside
                    className={clsx(
                        'fixed inset-y-0 left-0 z-30 w-64 bg-white dark:bg-gray-800 shadow-lg transform transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 lg:z-0',
                        {
                            'translate-x-0': sidebarOpen,
                            '-translate-x-full': !sidebarOpen,
                        }
                    )}
                >
                    <nav className="mt-20 lg:mt-5 px-4 space-y-1">
                        {navigation.map((item) => (
                            <NavLink
                                key={item.name}
                                to={item.href}
                                className={({isActive}) =>
                                    clsx(
                                        'group flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors',
                                        {
                                            'bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-200': isActive,
                                            'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-700': !isActive,
                                        }
                                    )
                                }
                            >
                                <item.icon className="mr-3 h-5 w-5"/>
                                {item.name}
                            </NavLink>
                        ))}
                    </nav>
                </aside>

                {/* Overlay для мобильных */}
                {sidebarOpen && (
                    <div
                        className="fixed inset-0 bg-gray-600 bg-opacity-75 z-20 lg:hidden"
                        onClick={toggleSidebar}
                    />
                )}

                {/* Main content */}
                <main className="flex-1 overflow-y-auto">
                    <div className="p-4 sm:p-6 lg:p-8">
                        <Outlet/>
                    </div>
                </main>
            </div>
        </div>
    );
}