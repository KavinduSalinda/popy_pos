export interface RequirementRow {
  product: string;
  sku: string;
  stock: number;
  soldLast30: number;
  perDay: number;
  need7: number;
  need30: number;
  need90: number;
  buy7: number;
  buy30: number;
  buy90: number;
}

export interface RequirementsReport {
  lookbackDays: number;
  rows: RequirementRow[];
  summary: {
    buy7: number;
    buy30: number;
    buy90: number;
  };
}

export interface InsightSettings {
  configured: boolean;
  keyHint: string;
}

export interface InsightWriting {
  summary: string;
  prediction: string;
}

export interface ChatTurn {
  role: 'user' | 'assistant';
  content: string;
}
