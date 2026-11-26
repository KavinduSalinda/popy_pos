import { useEffect, useRef, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import type { GridColDef } from '@mui/x-data-grid';
import { toast } from 'react-toastify';
import { PageHeader } from '@/components/common';
import { DataTable } from '@/components/tables';
import { formatQuantity } from '@/utils';
import { getErrorMessage } from '@/utils/error';
import {
  useAskInsightMutation,
  useGetInsightSettingsQuery,
  useGetRequirementsQuery,
  useSaveInsightKeyMutation,
  useWriteInsightSummaryMutation,
} from '../insightsApi';
import type { ChatTurn, RequirementRow } from '../types';

const quantityColumn = (
  field: keyof RequirementRow,
  headerName: string,
): GridColDef<RequirementRow & { id: number }> => ({
  field,
  headerName,
  flex: 0.7,
  minWidth: 110,
  valueFormatter: (value: number) => formatQuantity(value),
});

const columns: GridColDef<RequirementRow & { id: number }>[] = [
  { field: 'product', headerName: 'Product', flex: 1.2, minWidth: 160 },
  { field: 'sku', headerName: 'SKU', flex: 0.8, minWidth: 110 },
  quantityColumn('stock', 'Stock'),
  quantityColumn('soldLast30', 'Sold (30d)'),
  quantityColumn('perDay', 'Per day'),
  quantityColumn('need7', 'Need 7'),
  quantityColumn('need30', 'Need 30'),
  quantityColumn('need90', 'Need 90'),
  quantityColumn('buy7', 'Buy 7'),
  quantityColumn('buy30', 'Buy 30'),
  quantityColumn('buy90', 'Buy 90'),
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
  const rows = (report?.rows ?? []).map((row, index) => ({ id: index, ...row }));

  return (
    <>
      <PageHeader
        title="Insights"
        subtitle="Estimated from the last 30 days of sales. Figures are a guide for what to buy, not a promise."
      />

      {requirements.isLoading ? (
        <Box display="flex" justifyContent="center" py={6}>
          <CircularProgress />
        </Box>
      ) : requirements.isError ? (
        <Alert severity="error">{getErrorMessage(requirements.error)}</Alert>
      ) : (
        <Stack spacing={2}>
          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip label={`Buy 7 days: ${formatQuantity(report?.summary.buy7)}`} />
            <Chip label={`Buy 30 days: ${formatQuantity(report?.summary.buy30)}`} />
            <Chip label={`Buy 90 days: ${formatQuantity(report?.summary.buy90)}`} />
          </Stack>
          <DataTable rows={rows} columns={columns} paginationMode="client" />
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
