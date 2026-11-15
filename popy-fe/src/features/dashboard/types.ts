export interface DashboardSummary {
  todaySales: number;
  monthlySales: number;
  totalRevenue: number;
  grossProfit: number;
  lowStockCount: number;
  outOfStockCount: number;
  totalCustomers: number;
  totalSuppliers: number;
}

export interface SalesTrendPoint {
  label: string;
  total: number;
}

export interface SalesTrend {
  daily: SalesTrendPoint[];
  monthly: SalesTrendPoint[];
}

export interface TopProduct {
  productId: string | number;
  name: string;
  quantitySold: number;
  revenue: number;
}

export interface CategorySales {
  category: string;
  total: number;
}

export type DashboardRange = 7 | 30 | 90;

export interface MetricComparison {
  current: number;
  previous: number;
}

export interface DashboardKpis {
  totalSales: MetricComparison;
  transactions: MetricComparison;
  averageOrderValue: MetricComparison;
  grossProfit: MetricComparison;
  itemsPerTransaction: MetricComparison;
  refunds: MetricComparison;
}

export interface DashboardTrendPoint {
  label: string;
  current: number;
  previous: number;
}

export interface DashboardCategoryShare {
  category: string;
  total: number;
  share: number;
}

export interface DashboardLabeledTotal {
  label: string;
  total: number;
}

export interface DashboardTopProductRevenue {
  name: string;
  revenue: number;
}

export interface DashboardPaymentShare {
  method: string;
  count: number;
  share: number;
}

export interface DashboardCashierSales {
  name: string;
  total: number;
}

export interface DashboardLossPoint {
  label: string;
  discounts: number;
  refunds: number;
}

export interface DashboardLowStockItem {
  id: number;
  name: string;
  category: string;
  stock: number;
  reorderLevel: number;
  status: 'out' | 'low';
}

export interface DashboardRecentSale {
  reference: string;
  createdAt: string;
  cashier: string;
  paymentMethod: string;
  total: number;
}

export interface DashboardOverview {
  days: number;
  kpis: DashboardKpis;
  salesTrend: DashboardTrendPoint[];
  categories: DashboardCategoryShare[];
  salesByHour: DashboardLabeledTotal[];
  topProducts: DashboardTopProductRevenue[];
  paymentMethods: DashboardPaymentShare[];
  salesByCashier: DashboardCashierSales[];
  discountsAndRefunds: DashboardLossPoint[];
  lowStock: DashboardLowStockItem[];
  recentSales: DashboardRecentSale[];
}
