import {create} from 'zustand';
import {persist} from 'zustand/middleware';

interface AppState {
    // UI состояние
    darkMode: boolean;
    sidebarOpen: boolean;
    selectedDate: string;

    // Действия
    toggleDarkMode: () => void;
    toggleSidebar: () => void;
    setSelectedDate: (date: string) => void;
}

export const useAppStore = create<AppState>()(
    persist(
        (set) => ({
            darkMode: false,
            sidebarOpen: true,
            selectedDate: new Date().toISOString().split('T')[0],

            toggleDarkMode: () => set((state) => ({darkMode: !state.darkMode})),
            toggleSidebar: () => set((state) => ({sidebarOpen: !state.sidebarOpen})),
            setSelectedDate: (date) => set({selectedDate: date}),
        }),
        {
            name: 'app-storage',
            partialize: (state) => ({darkMode: state.darkMode}), // Сохраняем только тему
        }
    )
);