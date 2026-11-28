import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  CircularProgress,
  Paper,
  Stack,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material';
import type { GridColDef, GridPaginationModel } from '@mui/x-data-grid';
import { toast } from 'react-toastify';
import { EmptyState, PageHeader, SearchInput, StatusChip } from '@/components/common';
import { DataTable } from '@/components/tables';
import { formatQuantity, toNumber } from '@/utils';
import { getErrorMessage } from '@/utils/error';
import {
  useAskInsightMutation,
  useGetInsightSettingsQuery,
  useGetRequirementsQuery,
  useSaveInsightKeyMutation,
  useWriteInsightSummaryMutation,
} from '../insightsApi';
import { readRequirement, type HorizonDays, type RequirementReading } from '../present';
import type { ChatTurn, RequirementRow } from '../types';

type ProductView = 'order' | 'all';

type InsightRow = RequirementRow & RequirementReading & { id: string };

const HORIZONS: { days: HorizonDays; title: string; hint: string }[] = [
  { days: 7, title: 'Next 7 days', hint: 'Coming week' },
  { days: 30, title: 'Next 30 days', hint: 'Coming month' },
  { days: 90, title: 'Next 90 days', hint: 'Coming 3 months' },
];

const amountCell = (value: number): string =>
  value > 0 ? formatQuantity(value) : 'None';

const orderColor = (row: InsightRow): string => {
  if (row.toOrder <= 0) return 'text.secondary';
  if (row.tone === 'error') return 'error.main';
  return 'warning.main';
};

const columns: GridColDef<InsightRow>[] = [
  {
    field: 'product',
    headerName: 'Product',
    flex: 1.4,
    minWidth: 200,
    display: 'flex',
    renderCell: (params) => (
      <Box sx={{ minWidth: 0, lineHeight: 1.25 }}>
        <Typography variant="body2" fontWeight={600} noWrap>
          {params.row.product}
        </Typography>
        <Typography variant="caption" color="text.secondary" noWrap>
          {params.row.sku}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'stock',
    headerName: 'In stock',
    type: 'number',
    width: 110,
    valueFormatter: (value: number) => formatQuantity(value),
  },
  {
    field: 'perDay',
    headerName: 'Selling pace',
    type: 'number',
    flex: 1,
    minWidth: 180,
    align: 'left',
    headerAlign: 'left',
    display: 'flex',
    renderCell: (params) => (
      <Box sx={{ minWidth: 0, lineHeight: 1.25 }}>
        <Typography variant="body2" noWrap>
          {params.row.sellingPace}
        </Typography>
        <Typography variant="caption" color="text.secondary" noWrap>
          {toNumber(params.row.soldLast30) > 0
            ? `${formatQuantity(params.row.soldLast30)} sold in 30 days`
            : 'Nothing sold in 30 days'}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'coverDays',
    headerName: 'Stock lasts',
    type: 'number',
    flex: 1,
    minWidth: 160,
    align: 'left',
    headerAlign: 'left',
    display: 'flex',
    renderCell: (params) => (
      <Typography variant="body2">{params.row.stockLasts}</Typography>
    ),
  },
  {
    field: 'expectedSales',
    headerName: 'Expected sales',
    type: 'number',
    width: 150,
    align: 'right',
    headerAlign: 'right',
    display: 'flex',
    renderCell: (params) => (
      <Typography
        variant="body2"
        color={params.row.expectedSales > 0 ? 'text.primary' : 'text.secondary'}
      >
        {amountCell(params.row.expectedSales)}
      </Typography>
    ),
  },
  {
    field: 'toOrder',
    headerName: 'To order',
    type: 'number',
    flex: 1.1,
    minWidth: 220,
    align: 'left',
    headerAlign: 'left',
    display: 'flex',
    renderCell: (params) => (
      <Box sx={{ minWidth: 0, lineHeight: 1.25 }}>
        <Typography
          variant="body2"
          fontWeight={params.row.toOrder > 0 ? 700 : 400}
          color={orderColor(params.row)}
        >
          {amountCell(params.row.toOrder)}
        </Typography>
        <Typography variant="caption" color="text.secondary" noWrap>
          {params.row.otherPeriods}
        </Typography>
      </Box>
    ),
  },
  {
    field: 'advice',
    headerName: 'What to do',
    width: 150,
    display: 'flex',
    renderCell: (params) => (
      <StatusChip label={params.row.advice} color={params.row.tone} />
    ),
  },
];

const plainInsightText = (value: string): string => {
  const cleaned = value
    .replace(/[\u00a0\u202f\u2009]/g, ' ')
    .replace(/^#{1,6}\s+/gm, '')
    .replace(/\*\*|__|`/g, '')
    .replace(
      /\s*\((?:the\s+)?["“”']?(?:buy90|buy30|buy7|need90|need30|need7|per_day)["“”']?(?:\s+figure)?\)/gi,
      '',
    )
    .replace(/\b(?:buy90|buy30|buy7|need90|need30|need7|per_day)\b/gi, '')
    .replace(/^\s*(?:[-*]|\d+[.)])\s+/gm, '')
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/ +\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
  if (/^{}+$/.test(cleaned)) {
    return 'Ask what to buy for the next 7, 30, or 90 days.';
  }
  return cleaned;
};

const InsightText = ({ text }: { text: string }) => (
  <Typography
    variant="body2"
    sx={{ whiteSpace: 'pre-line', lineHeight: 1.7 }}
  >
    {plainInsightText(text)}
  </Typography>
);

export const InsightsPage = () => {
  const requirements = useGetRequirementsQuery();
  const settings = useGetInsightSettingsQuery();
  const [saveKey, { isLoading: savingKey }] = useSaveInsightKeyMutation();
  const [writeSummary, summaryState] = useWriteInsightSummaryMutation();
  const [ask, askState] = useAskInsightMutation();
  const [apiKey, setApiKey] = useState('');
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [horizon, setHorizon] = useState<HorizonDays>(30);
  const [view, setView] = useState<ProductView>('order');
  const [query, setQuery] = useState('');
  const [paginationModel, setPaginationModel] = useState<GridPaginationModel>({
    page: 0,
    pageSize: 10,
  });

  const configured = Boolean(settings.data?.configured);
  const requestedSummary = useRef(false);

  useEffect(() => {
    if (!configured || requestedSummary.current) return;
    requestedSummary.current = true;
    void writeSummary();
  }, [configured, writeSummary]);

  const handleSaveKey = async () => {
    const trimmed = apiKey.trim();
    if (!trimmed) {
      toast.error('Paste a Groq API key first.');
      return;
    }
    try {
      await saveKey({ apiKey: trimmed }).unwrap();
      setApiKey('');
      toast.success('Groq key saved for this shop');
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  const handleAsk = async () => {
    const trimmed = question.trim();
    if (!trimmed) return;
    const history = messages.slice(-6).map((message) => ({
      role: message.role,
      content: message.content.slice(0, 1000),
    }));
    setQuestion('');
    setMessages((current) => [...current, { role: 'user', content: trimmed }]);
    try {
      const result = await ask({ question: trimmed, history }).unwrap();
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: result.answer },
      ]);
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'assistant', content: getErrorMessage(error) },
      ]);
    }
  };

  const report = requirements.data;
  const sourceRows = report?.rows;

  const readings = useMemo(() => {
    const seen = new Map<string, number>();
    return (sourceRows ?? [])
      .map((row) => {
        const base = row.sku || row.product;
        const count = seen.get(base) ?? 0;
        seen.set(base, count + 1);
        return {
          id: count === 0 ? base : `${base}-${count}`,
          ...row,
          ...readRequirement(row, horizon),
        };
      })
      .sort(
        (a, b) =>
          b.toOrder - a.toOrder ||
          a.coverDays - b.coverDays ||
          a.product.localeCompare(b.product),
      );
  }, [sourceRows, horizon]);

  const ordering = readings.filter((row) => row.toOrder > 0);
  const pool = view === 'order' ? ordering : readings;
  const needle = query.trim().toLowerCase();
  const rows = needle
    ? pool.filter((row) =>
        `${row.product} ${row.sku}`.toLowerCase().includes(needle),
      )
    : pool;

  const catalog = sourceRows ?? [];
  const unitsFor = (days: HorizonDays) => toNumber(report?.summary[`buy${days}`]);
  const shortFor = (days: HorizonDays) =>
    catalog.filter((row) => toNumber(row[`buy${days}`]) > 0).length;

  const showPage = (nextPage: number) =>
    setPaginationModel((current) => ({ ...current, page: nextPage }));

  const empty =
    catalog.length === 0
      ? {
          title: 'No products yet',
          description: 'Active products show up here once they are in the catalog.',
          showAll: false,
        }
      : view === 'order' && ordering.length === 0
        ? {
            title: 'Nothing to order',
            description: `You already have enough stock for the next ${horizon} days.`,
            showAll: true,
          }
        : {
            title: 'No matching products',
            description: 'Try another name or product code.',
            showAll: false,
          };

  return (
    <>
      <PageHeader
        title="Insights"
        subtitle="What to order next, based on how each product sold over the last 30 days. These are estimates, not a promise."
      />

      {requirements.isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : requirements.isError ? (
        <Alert severity="error">{getErrorMessage(requirements.error)}</Alert>
      ) : (
        <Stack spacing={2}>
          <Box
            sx={{
              display: 'grid',
              gap: 2,
              gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
            }}
          >
            {HORIZONS.map((item) => {
              const selected = horizon === item.days;
              const units = unitsFor(item.days);
              const shortCount = shortFor(item.days);
              return (
                <Card
                  key={item.days}
                  component="button"
                  type="button"
                  aria-pressed={selected}
                  onClick={() => {
                    setHorizon(item.days);
                    showPage(0);
                  }}
                  sx={{
                    textAlign: 'left',
                    font: 'inherit',
                    color: 'inherit',
                    cursor: 'pointer',
                    width: '100%',
                    p: 0,
                    boxShadow: 'none',
                    borderStyle: 'solid',
                    borderWidth: 1,
                    borderColor: selected ? 'primary.main' : 'divider',
                    bgcolor: selected ? 'action.selected' : 'background.paper',
                  }}
                >
                  <CardContent sx={{ p: 2, '&:last-child': { pb: 2 } }}>
                    <Typography sx={{ color: 'text.secondary', fontSize: 12 }}>
                      {item.hint}
                    </Typography>
                    <Typography variant="subtitle1" fontWeight={700}>
                      {item.title}
                    </Typography>
                    <Typography sx={{ fontSize: 28, fontWeight: 700, lineHeight: 1.2, my: 0.5 }}>
                      {formatQuantity(units)}
                    </Typography>
                    <Typography sx={{ color: 'text.secondary', fontSize: 12, mb: 0.5 }}>
                      units to order
                    </Typography>
                    <Typography
                      sx={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: shortCount > 0 ? 'warning.main' : 'success.main',
                      }}
                    >
                      {catalog.length === 0
                        ? 'No products yet'
                        : shortCount === 0
                          ? 'Every product is covered'
                          : shortCount === 1
                            ? '1 product is short'
                            : `${shortCount} products are short`}
                    </Typography>
                  </CardContent>
                </Card>
              );
            })}
          </Box>

          <Stack
            direction={{ xs: 'column', lg: 'row' }}
            spacing={2}
            justifyContent="space-between"
            alignItems={{ lg: 'flex-end' }}
          >
            <Box>
              <Typography variant="subtitle1" fontWeight={700}>
                What to order for the next {horizon} days
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 640 }}>
                Expected sales is based on the last 30 days. To order is that amount minus
                the stock you already have. The note under it covers the other two periods.
              </Typography>
            </Box>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems={{ sm: 'center' }}>
              <ToggleButtonGroup
                exclusive
                size="small"
                value={view}
                aria-label="Which products to show"
                onChange={(_, next: ProductView | null) => {
                  if (!next) return;
                  setView(next);
                  showPage(0);
                }}
              >
                <ToggleButton value="order">Needs an order</ToggleButton>
                <ToggleButton value="all">All products</ToggleButton>
              </ToggleButtonGroup>
              <SearchInput
                placeholder="Search products"
                onSearch={(value) => {
                  setQuery(value);
                  showPage(0);
                }}
              />
            </Stack>
          </Stack>

          {rows.length === 0 ? (
            <Paper variant="outlined">
              <EmptyState
                title={empty.title}
                description={empty.description}
                action={
                  empty.showAll ? (
                    <Button
                      variant="outlined"
                      onClick={() => {
                        setView('all');
                        showPage(0);
                      }}
                    >
                      Show all products
                    </Button>
                  ) : undefined
                }
              />
            </Paper>
          ) : (
            <DataTable
              rows={rows}
              columns={columns}
              paginationMode="client"
              paginationModel={paginationModel}
              onPaginationModelChange={setPaginationModel}
              rowHeight={64}
              getRowClassName={(params) => {
                if (params.row.tone === 'error') return 'insight-urgent';
                if (params.row.tone === 'warning') return 'insight-soon';
                return '';
              }}
              sx={{
                '& .MuiDataGrid-row.insight-urgent': {
                  bgcolor: 'rgba(220, 38, 38, 0.08)',
                },
                '& .MuiDataGrid-row.insight-urgent:hover, & .MuiDataGrid-row.insight-urgent.Mui-hovered':
                  {
                    bgcolor: 'rgba(220, 38, 38, 0.14)',
                  },
                '& .MuiDataGrid-row.insight-soon': {
                  bgcolor: 'rgba(217, 119, 6, 0.08)',
                },
                '& .MuiDataGrid-row.insight-soon:hover, & .MuiDataGrid-row.insight-soon.Mui-hovered':
                  {
                    bgcolor: 'rgba(217, 119, 6, 0.14)',
                  },
              }}
            />
          )}
        </Stack>
      )}

      <Stack spacing={2} sx={{ mt: 3 }}>
        {!configured ? (
          <Card>
            <CardContent>
              <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                Written forecast
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                The table above does not need an AI key. To add a written
                explanation and ask questions, create a free key at
                console.groq.com and save it for this shop.
              </Typography>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
                <TextField
                  label="Groq API key"
                  type="password"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  size="small"
                  fullWidth
                />
                <Button
                  variant="contained"
                  onClick={() => void handleSaveKey()}
                  disabled={savingKey}
                >
                  {savingKey ? 'Saving…' : 'Save key'}
                </Button>
              </Stack>
            </CardContent>
          </Card>
        ) : (
          <Stack direction={{ xs: 'column', md: 'row' }} spacing={2}>
            <Card sx={{ flex: 1 }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  Recent trading
                </Typography>
                {summaryState.isLoading ? (
                  <CircularProgress size={22} />
                ) : summaryState.isError ? (
                  <Alert severity="warning">
                    {getErrorMessage(summaryState.error)}
                  </Alert>
                ) : (
                  <InsightText
                    text={
                      summaryState.data?.summary ||
                      'The summary will appear here.'
                    }
                  />
                )}
                {settings.data?.keyHint ? (
                  <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 2 }}>
                    Groq key {settings.data.keyHint}
                  </Typography>
                ) : null}
              </CardContent>
            </Card>
            <Card sx={{ flex: 1 }}>
              <CardContent>
                <Typography variant="subtitle1" fontWeight={600} gutterBottom>
                  What to buy
                </Typography>
                {summaryState.isLoading ? (
                  <CircularProgress size={22} />
                ) : (
                  <InsightText
                    text={
                      summaryState.data?.prediction ||
                      'The forecast will appear here.'
                    }
                  />
                )}
              </CardContent>
            </Card>
          </Stack>
        )}

        <Card>
          <CardContent>
            <Typography variant="subtitle1" fontWeight={600} gutterBottom>
              Ask about this report
            </Typography>
            <Stack spacing={1.5} sx={{ mb: 2, maxHeight: 460, overflow: 'auto' }}>
              {messages.length === 0 ? (
                <Typography variant="body2" color="text.secondary">
                  Ask which products to order, or what the next 90 days may need.
                </Typography>
              ) : (
                messages.map((message, index) => (
                  <Box
                    key={`${message.role}-${index}`}
                    sx={
                      message.role === 'assistant'
                        ? {
                            bgcolor: 'action.hover',
                            borderRadius: 2,
                            px: 1.5,
                            py: 1.25,
                          }
                        : undefined
                    }
                  >
                    <Typography variant="caption" color="text.secondary">
                      {message.role === 'user' ? 'You' : 'Insights'}
                    </Typography>
                    {message.role === 'assistant' ? (
                      <InsightText text={message.content} />
                    ) : (
                      <Typography variant="body2">{message.content}</Typography>
                    )}
                  </Box>
                ))
              )}
            </Stack>
            <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1}>
              <TextField
                label="Question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                size="small"
                fullWidth
                disabled={!configured || askState.isLoading}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    void handleAsk();
                  }
                }}
              />
              <Button
                variant="contained"
                onClick={() => void handleAsk()}
                disabled={!configured || askState.isLoading || !question.trim()}
              >
                {askState.isLoading ? 'Asking…' : 'Ask'}
              </Button>
            </Stack>
          </CardContent>
        </Card>
      </Stack>
    </>
  );
};

export default InsightsPage;
