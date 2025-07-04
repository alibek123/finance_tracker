// Базовые типы данных, соответствующие вашему API

export interface Account {
  id: number;
  name: string;
  type: 'cash' | 'debit_card' | 'credit_card' | 'savings' | 'investment';
  initial_balance: number;
  current_balance: number;
  currency: string;
  icon?: string;
  color?: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  transaction_count?: number;
}

export interface Category {
  id: number;
  name: string;
  parent_id?: number;
  type: 'expense' | 'income' | 'transfer';
  icon?: string;
  color?: string;
  is_active: boolean;
  level?: number;
  path?: string;
}

export interface Transaction {
  id: number;
  date: string;
  type: 'expense' | 'income' | 'transfer' | 'correction';
  amount: number;
  account_from_id?: number;
  account_to_id?: number;
  category_id?: number;
  subcategory_id?: number;
  description?: string;
  notes?: string;
  is_planned: boolean;
  tags?: string[];
  // Дополнительные поля из JOIN
  category_name?: string;
  category_icon?: string;
  category_color?: string;
  subcategory_name?: string;
  account_from_name?: string;
  account_to_name?: string;
}

export interface Tag {
  id: number;
  name: string;
  color?: string;
  created_at: string;
}

export interface Budget {
  id: number;
  name: string;
  category_id: number;
  amount: number;
  period: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';
  start_date: string;
  end_date?: string;
  is_active: boolean;
  // Вычисляемые поля
  spent_amount?: number;
  usage_percentage?: number;
  category_name?: string;
  category_icon?: string;
  category_color?: string;
}

export interface SavingsGoal {
  id: number;
  name: string;
  target_amount: number;
  current_amount: number;
  target_date?: string;
  account_id?: number;
  notes?: string;
  is_achieved: boolean;
  created_at: string;
  achieved_at?: string;
  account_name?: string;
}

export interface RecurringTransaction {
  id: number;
  name: string;
  type: 'expense' | 'income';
  amount: number;
  account_from_id?: number;
  account_to_id?: number;
  category_id?: number;
  frequency: 'daily' | 'weekly' | 'monthly' | 'quarterly' | 'yearly';
  start_date: string;
  end_date?: string;
  is_active: boolean;
  last_created_date?: string;
  category_name?: string;
}

export interface DashboardStats {
  total_balance: number;
  total_income: number;
  total_expense: number;
  net_balance: number;
  net_savings: number;
  daily_expenses: Array<{
    date: string;
    amount: number;
  }>;
  category_breakdown: Array<{
    category_name: string;
    amount: number;
    color?: string;
    icon?: string;
  }>;
}