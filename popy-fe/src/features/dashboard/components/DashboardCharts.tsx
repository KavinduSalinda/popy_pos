import { Box, Card, CardContent, Typography, useTheme } from '@mui/material';
import type { ReactNode } from 'react';
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  Pie,
  PieChart,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { formatCurrency, toNumber } from '@/utils';
import type {
  DashboardCashierSales,
  DashboardCategoryShare,
  DashboardLabeledTotal,
  DashboardLossPoint,
  DashboardPaymentShare,
  DashboardTopProductRevenue,
  DashboardTrendPoint,
} from '../types';

const CHART_COLORS = [
  '#1f5eff',
  '#12b886',
  '#f59f00',
  '#e8590c',
  '#7950f2',
  '#15aabf',
  '#e64980',
];

const PAYMENT_COLORS: Record<string, string> = {
  Cash: CHART_COLORS[1],
  Card: CHART_COLORS[0],
  Mobile: CHART_COLORS[4],
  QR: CHART_COLORS[4],
  Credit: CHART_COLORS[2],
};

const shortNumber = (value: number) => {
  const amount = Math.abs(toNumber(value));
  const signed = toNumber(value) < 0 ? '-' : '';
  if (amount >= 1_000_000) return `${signed}${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `${signed}${Math.round(amount / 1_000)}k`;
  return `${Math.round(toNumber(value))}`;
};

const truncate = (value: string, length = 22) =>
  value.length > length ? `${value.slice(0, length - 1)}…` : value;

interface ChartCardProps {
  title: string;
  subtitle: string;
  tall?: boolean;
  /** Tables size to their rows. Charts keep a fixed plot height. */
  fluid?: boolean;
  children: ReactNode;
}

export const ChartCard = ({
  title,
  subtitle,
  tall = false,
  fluid = false,
  children,
}: ChartCardProps) => (
  <Card
    sx={{
      height: '100%',
      border: '1px solid',
      borderColor: 'divider',
      boxShadow: 'none',
      minWidth: 0,
    }}
  >
    <CardContent sx={{ p: 2, '&:last-child': { pb: 2 }, minWidth: 0 }}>
      <Typography sx={{ fontSize: 14, fontWeight: 600 }}>{title}</Typography>
      <Typography sx={{ color: 'text.secondary', fontSize: 12, mb: 1.25 }}>
        {subtitle}
      </Typography>
      <Box sx={fluid ? { overflowX: 'auto' } : { height: tall ? 300 : 260, minWidth: 0 }}>
        {children}
      </Box>
    </CardContent>
  </Card>
);

export const ChartEmpty = ({ label }: { label: string }) => (
  <Box sx={{ height: '100%', display: 'grid', placeItems: 'center' }}>
    <Typography sx={{ color: 'text.secondary', fontSize: 13 }}>{label}</Typography>
  </Box>
);

const useAxis = () => {
  const theme = useTheme();
  return {
    tick: { fill: theme.palette.text.secondary, fontSize: 11 },
    grid: theme.palette.divider,
    paper: theme.palette.background.paper,
    cursor: theme.palette.action.hover,
  };
};

const MoneyTooltip = ({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number; color?: string }>;
  label?: string;
}) => {
  const theme = useTheme();
  if (!active || !payload?.length) return null;
  return (
    <Box
      sx={{
        bgcolor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        px: 1.25,
        py: 0.75,
        boxShadow: theme.shadows[1],
      }}
    >
      {label ? (
        <Typography sx={{ fontSize: 12, fontWeight: 600, mb: 0.25 }}>{label}</Typography>
      ) : null}
      {payload.map((entry) => (
        <Typography key={entry.name} sx={{ fontSize: 12, color: entry.color }}>
          {entry.name}: {formatCurrency(entry.value)}
        </Typography>
      ))}
    </Box>
  );
};

export const SalesTrendChart = ({ data }: { data: DashboardTrendPoint[] }) => {
  const axis = useAxis();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={axis.grid} vertical={false} />
        <XAxis
          dataKey="label"
          tick={axis.tick}
          tickLine={false}
          axisLine={false}
          minTickGap={28}
        />
        <YAxis
          tick={axis.tick}
          tickFormatter={shortNumber}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip content={<MoneyTooltip />} />
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
        <Area
          type="monotone"
          dataKey="current"
          name="This period"
          stroke={CHART_COLORS[0]}
          fill={CHART_COLORS[0]}
          fillOpacity={0.13}
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="previous"
          name="Previous period"
          stroke={CHART_COLORS[2]}
          strokeDasharray="5 4"
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
};

export const CategoryChart = ({ data }: { data: DashboardCategoryShare[] }) => {
  const axis = useAxis();
  if (data.length === 0) return <ChartEmpty label="No category sales in this period" />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="share"
          nameKey="category"
          innerRadius="62%"
          outerRadius="78%"
          paddingAngle={2}
          stroke={axis.paper}
          strokeWidth={2}
        >
          {data.map((entry, index) => (
            <Cell key={entry.category} fill={CHART_COLORS[index % CHART_COLORS.length]} />
          ))}
        </Pie>
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const row = payload[0].payload as DashboardCategoryShare;
            return (
              <Box
                sx={{
                  bgcolor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  px: 1.25,
                  py: 0.75,
                }}
              >
                <Typography sx={{ fontSize: 12 }}>
                  {row.category}: {toNumber(row.share)}% · {formatCurrency(row.total)}
                </Typography>
              </Box>
            );
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export const HourChart = ({ data }: { data: DashboardLabeledTotal[] }) => {
  const axis = useAxis();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={axis.grid} vertical={false} />
        <XAxis
          dataKey="label"
          tick={axis.tick}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={axis.tick}
          tickFormatter={shortNumber}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: axis.cursor }} />
        <Bar
          dataKey="total"
          name="Sales"
          fill={CHART_COLORS[0]}
          radius={[4, 4, 0, 0]}
          maxBarSize={28}
        />
      </BarChart>
    </ResponsiveContainer>
  );
};

export const TopProductsChart = ({ data }: { data: DashboardTopProductRevenue[] }) => {
  const axis = useAxis();
  if (data.length === 0) return <ChartEmpty label="No product sales in this period" />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={data}
        layout="vertical"
        margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
      >
        <CartesianGrid stroke={axis.grid} horizontal={false} />
        <XAxis
          type="number"
          tick={axis.tick}
          tickFormatter={shortNumber}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={128}
          tick={axis.tick}
          tickFormatter={(value: string) => truncate(value)}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: axis.cursor }} />
        <Bar
          dataKey="revenue"
          name="Revenue"
          fill={CHART_COLORS[1]}
          radius={[0, 4, 4, 0]}
          maxBarSize={18}
        />
      </BarChart>
    </ResponsiveContainer>
  );
};

export const PaymentChart = ({ data }: { data: DashboardPaymentShare[] }) => {
  const axis = useAxis();
  if (data.length === 0) return <ChartEmpty label="No payments in this period" />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data}
          dataKey="share"
          nameKey="method"
          outerRadius="78%"
          stroke={axis.paper}
          strokeWidth={2}
        >
          {data.map((entry) => (
            <Cell
              key={entry.method}
              fill={PAYMENT_COLORS[entry.method] ?? CHART_COLORS[0]}
            />
          ))}
        </Pie>
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            const row = payload[0].payload as DashboardPaymentShare;
            return (
              <Box
                sx={{
                  bgcolor: 'background.paper',
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  px: 1.25,
                  py: 0.75,
                }}
              >
                <Typography sx={{ fontSize: 12 }}>
                  {row.method}: {toNumber(row.share)}%
                </Typography>
              </Box>
            );
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
};

export const CashierChart = ({ data }: { data: DashboardCashierSales[] }) => {
  const axis = useAxis();
  if (data.length === 0) return <ChartEmpty label="No cashier sales in this period" />;
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={axis.grid} vertical={false} />
        <XAxis
          dataKey="name"
          tick={axis.tick}
          tickLine={false}
          axisLine={false}
          interval={0}
        />
        <YAxis
          tick={axis.tick}
          tickFormatter={shortNumber}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip content={<MoneyTooltip />} cursor={{ fill: axis.cursor }} />
        <Bar
          dataKey="total"
          name="Sales"
          fill={CHART_COLORS[4]}
          radius={[4, 4, 0, 0]}
          maxBarSize={36}
        />
      </BarChart>
    </ResponsiveContainer>
  );
};

export const LossChart = ({ data }: { data: DashboardLossPoint[] }) => {
  const axis = useAxis();
  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={axis.grid} vertical={false} />
        <XAxis
          dataKey="label"
          tick={axis.tick}
          tickLine={false}
          axisLine={false}
          minTickGap={16}
        />
        <YAxis
          tick={axis.tick}
          tickFormatter={shortNumber}
          tickLine={false}
          axisLine={false}
          width={44}
        />
        <Tooltip content={<MoneyTooltip />} />
        <Legend iconSize={10} wrapperStyle={{ fontSize: 12 }} />
        <Line
          type="monotone"
          dataKey="discounts"
          name="Discounts"
          stroke={CHART_COLORS[2]}
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="refunds"
          name="Refunds"
          stroke={CHART_COLORS[3]}
          strokeWidth={2}
          dot={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
};
