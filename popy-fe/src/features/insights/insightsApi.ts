import { baseApi } from '@/api/baseApi';
import type {
  ChatTurn,
  InsightSettings,
  InsightWriting,
  RequirementsReport,
} from './types';

export const insightsApi = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getRequirements: builder.query<RequirementsReport, void>({
      query: () => ({ url: '/insights/requirements' }),
      providesTags: [{ type: 'Insight', id: 'REQUIREMENTS' }],
    }),
    getInsightSettings: builder.query<InsightSettings, void>({
      query: () => ({ url: '/insights/settings' }),
      providesTags: [{ type: 'Insight', id: 'SETTINGS' }],
    }),
    saveInsightKey: builder.mutation<InsightSettings, { apiKey: string }>({
      query: (body) => ({
        url: '/insights/settings',
        method: 'PUT',
        data: body,
      }),
      invalidatesTags: [{ type: 'Insight', id: 'SETTINGS' }],
    }),
    writeInsightSummary: builder.mutation<InsightWriting, void>({
      query: () => ({
        url: '/insights/summary',
        method: 'POST',
      }),
    }),
    askInsight: builder.mutation<
      { answer: string },
      { question: string; history: ChatTurn[] }
    >({
      query: (body) => ({
        url: '/insights/ask',
        method: 'POST',
        data: body,
      }),
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetRequirementsQuery,
  useGetInsightSettingsQuery,
  useSaveInsightKeyMutation,
  useWriteInsightSummaryMutation,
  useAskInsightMutation,
} = insightsApi;
