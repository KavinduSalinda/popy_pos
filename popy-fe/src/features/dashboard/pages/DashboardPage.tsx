import { useState } from 'react';
import {
  Alert,
  Box,
  MenuItem,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from '@mui/material';
import dayjs from 'dayjs';
import { Loader, PageHeader } from '@/components/common';
import { formatCurrency, formatNumber, formatQuantity, toNumber } from '@/utils';
import {
  CashierChart,
  CategoryChart,
  ChartCard,
  HourChart,
  LossChart,
  PaymentChart,
  SalesTrendChart,
  TopProductsChart,
} from '../components/DashboardCharts';
import { KpiCard } from '../components/KpiCard';
import { useGetDashboardOverviewQuery } from '../dashboardApi';
import type { DashboardOverview, DashboardRange } from '../types';

const RANGES: { value: DashboardRange; label: string }[] = [
  { value: 7, label: 'Last 7 days' },
  { value: 30, label: 'Last 30 days' },
  { value: 90, label: 'Last 90 days' },
];

const grid = {
  display: 'grid',
  gap: 2,
  '& > *': { minWidth: 0 },
};

const tableSx = {
  minWidth: 420,
  '& .MuiTableCell-root': { borderColor: 'divider', py: '9px', px: '6px' },
  '& .MuiTableCell-head': { fontWeight: 600 },
  '& .MuiTableBody-root .MuiTableRow-root:last-child .MuiTableCell-root': {
    borderBottom: 0,
  },
};

const formatSaleTime = (value: string) => {
  const parsed = dayjs(value);
  if (!parsed.isValid()) return '-';
  return parsed.isSame(dayjs(), 'day')
    ? parsed.format('h:mm a')
    : parsed.format('D MMM, h:mm a');
};

const DashboardBody = ({ data }: { data: DashboardOverview }) => {
  const kpis = data.kpis;
  const cards = [
    {
      title: 'Total sales',
      value: formatCurrency(kpis.totalSales.current),
      metric: kpis.totalSales,
    },
    {
      title: 'Transactions',
      value: formatNumber(kpis.transactions.current),
      metric: kpis.transactions,
    },
    {
      title: 'Average order value',
      value: formatCurrency(kpis.averageOrderValue.current),
      metric: kpis.averageOrderValue,
    },
    {
      title: 'Gross profit',
      value: formatCurrency(kpis.grossProfit.current),
      metric: kpis.grossProfit,
    },
    {
      title: 'Items per transaction',
      value: toNumber(kpis.itemsPerTransaction.current).toFixed(1),
      metric: kpis.itemsPerTransaction,
    },
    {
      title: 'Refunds',
      value: formatCurrency(kpis.refunds.current),
      metric: kpis.refunds,
      inverse: true,
    },
  ];

  return (
    <>
      <Box
        sx={{
          ...grid,
          gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))',
        }}
      >
        {cards.map((card) => (
          <KpiCard
            key={card.title}
            title={card.title}
            value={card.value}
            current={toNumber(card.metric.current)}
            previous={toNumber(card.metric.previous)}
            inverse={card.inverse}
          />
        ))}
      </Box>

      <Box
        sx={{
          ...grid,
          gridTemplateColumns: { xs: '1fr', lg: '2fr 1fr' },
        }}
      >
        <ChartCard title="Sales trend" subtitle="Daily sales vs the previous period" tall>
          <SalesTrendChart data={data.salesTrend} />
        </ChartCard>
        <ChartCard title="Sales by category" subtitle="Share of revenue" tall>
          <CategoryChart data={data.categories} />
        </ChartCard>
      </Box>

      <Box
        sx={{
          ...grid,
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr', lg: 'repeat(3, 1fr)' },
        }}
      >
        <ChartCard title="Sales by hour" subtitle="Find your busiest hours">
          <HourChart data={data.salesByHour} />
        </ChartCard>
        <ChartCard title="Top products" subtitle="By revenue">
          <TopProductsChart data={data.topProducts} />
        </ChartCard>
        <ChartCard title="Payment methods" subtitle="Share of transactions">
          <PaymentChart data={data.paymentMethods} />
        </ChartCard>
      </Box>

      <Box sx={{ ...grid, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
        <ChartCard title="Sales by cashier" subtitle="Revenue per person">
          <CashierChart data={data.salesByCashier} />
        </ChartCard>
        <ChartCard title="Discounts and refunds" subtitle="Watch for spikes">
          <LossChart data={data.discountsAndRefunds} />
        </ChartCard>
      </Box>

      <Box sx={{ ...grid, gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' } }}>
        <ChartCard title="Low stock" subtitle="Items at or below reorder level" fluid>
          <Box>
            <Table size="small" sx={tableSx}>
              <TableHead>
                <TableRow>
                  <TableCell>Product</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell align="right">Stock</TableCell>
                  <TableCell align="right">Reorder at</TableCell>
                  <TableCell>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.lowStock.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      sx={{ color: 'text.secondary', borderBottom: 0 }}
                    >
                      Nothing is at or below its reorder level.
                    </TableCell>
                  </TableRow>
                ) : (
                  data.lowStock.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell>{item.name}</TableCell>
                      <TableCell>{item.category}</TableCell>
                      <TableCell align="right">{formatQuantity(item.stock)}</TableCell>
                      <TableCell align="right">
                        {formatQuantity(item.reorderLevel)}
                      </TableCell>
                      <TableCell>
                        <Box
                          component="span"
                          sx={{
                            borderRadius: '12px',
                            px: '9px',
                            py: '2px',
                            fontSize: 12,
                            fontWeight: 500,
                            color: '#fff',
                            bgcolor: item.status === 'out' ? '#dc2626' : '#d97706',
                          }}
                        >
                          {item.status === 'out' ? 'Out of stock' : 'Low'}
                        </Box>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Box>
        </ChartCard>

        <ChartCard title="Recent sales" subtitle="Latest completed transactions" fluid>
          <Box>
            <Table size="small" sx={tableSx}>
              <TableHead>
                <TableRow>
                  <TableCell>Invoice</TableCell>
                  <TableCell>Time</TableCell>
                  <TableCell>Cashier</TableCell>
                  <TableCell>Payment</TableCell>
                  <TableCell align="right">Total</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {data.recentSales.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={5}
                      sx={{ color: 'text.secondary', borderBottom: 0 }}
                    >
                      No sales yet.
                    </TableCell>
                  </TableRow>
                ) : (
                  data.recentSales.map((sale) => (
                    <TableRow key={sale.reference}>
                      <TableCell>{sale.reference}</TableCell>
                      <TableCell>{formatSaleTime(sale.createdAt)}</TableCell>
                      <TableCell>{sale.cashier}</TableCell>
                      <TableCell>{sale.paymentMethod}</TableCell>
                      <TableCell align="right">{formatCurrency(sale.total)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Box>
        </ChartCard>
      </Box>

      <Typography sx={{ color: 'text.secondary', fontSize: 12 }}>
        Compared with the previous period of the same length. Figures update as sales are
        processed.
      </Typography>
    </>
  );
};

export const DashboardPage = () => {
  const [days, setDays] = useState<DashboardRange>(30);
  const { data, isLoading, isFetching, isError } = useGetDashboardOverviewQuery(days);

  return (
    <Box
      sx={{
        display: 'grid',
        gap: 2,
        opacity: isFetching && data ? 0.72 : 1,
        transition: 'opacity 160ms ease',
      }}
    >
      <PageHeader
        title="Dashboard"
        actions={
          <TextField
            select
            size="small"
            value={days}
            onChange={(event) => setDays(Number(event.target.value) as DashboardRange)}
            aria-label="Date range"
            sx={{ minWidth: 168, '& .MuiOutlinedInput-root': { borderRadius: 2 } }}
          >
            {RANGES.map((range) => (
              <MenuItem key={range.value} value={range.value}>
                {range.label}
              </MenuItem>
            ))}
          </TextField>
        }
      />

      {isError && !data ? (
        <Alert severity="error">
          The dashboard could not be loaded. Try again in a moment.
        </Alert>
      ) : null}

      {isLoading && !data ? <Loader message="Loading dashboard…" /> : null}
      {data ? <DashboardBody data={data} /> : null}
    </Box>
  );
};

export default DashboardPage;
