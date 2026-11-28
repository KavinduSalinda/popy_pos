import { Card, CardContent, Skeleton, Typography } from '@mui/material';
import { toNumber } from '@/utils';

interface KpiCardProps {
  title: string;
  value: string;
  current: number;
  previous: number;
  /** When true, a decrease is the favorable direction (refunds). */
  inverse?: boolean;
  loading?: boolean;
}

export interface DeltaPresentation {
  text: string;
  /** Null is a flat change and uses the neutral text color. */
  favorable: boolean | null;
}

export const deltaPresentation = (
  current: number,
  previous: number,
  inverse: boolean,
): DeltaPresentation => {
  const currentValue = toNumber(current);
  const previousValue = toNumber(previous);
  if (previousValue === 0) {
    if (currentValue === 0) return { text: '0.0% vs previous', favorable: null };
    const up = currentValue > 0;
    return {
      text: `${up ? '▲' : '▼'} New vs previous`,
      favorable: inverse ? currentValue < 0 : currentValue > 0,
    };
  }
  const change = ((currentValue - previousValue) / Math.abs(previousValue)) * 100;
  if (Math.abs(change) < 0.05) return { text: '0.0% vs previous', favorable: null };
  const rose = change > 0;
  return {
    text: `${rose ? '▲' : '▼'} ${Math.abs(change).toFixed(1)}% vs previous`,
    favorable: inverse ? change < 0 : change > 0,
  };
};

export const KpiCard = ({
  title,
  value,
  current,
  previous,
  inverse = false,
  loading = false,
}: KpiCardProps) => {
  const delta = deltaPresentation(toNumber(current), toNumber(previous), inverse);

  return (
    <Card
      sx={{
        height: '100%',
        border: '1px solid',
        borderColor: 'divider',
        boxShadow: 'none',
      }}
    >
      <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
        <Typography sx={{ color: 'text.secondary', fontSize: 12 }}>{title}</Typography>
        {loading ? (
          <Skeleton width={96} height={32} sx={{ my: 0.5 }} />
        ) : (
          <Typography sx={{ fontSize: 22, fontWeight: 600, my: 0.5, lineHeight: 1.2 }}>
            {value}
          </Typography>
        )}
        {loading ? (
          <Skeleton width={120} height={16} />
        ) : (
          <Typography
            sx={{
              fontSize: 12,
              fontWeight: 500,
              color:
                delta.favorable === null
                  ? 'text.secondary'
                  : delta.favorable
                    ? 'success.main'
                    : 'error.main',
            }}
          >
            {delta.text}
          </Typography>
        )}
      </CardContent>
    </Card>
  );
};
