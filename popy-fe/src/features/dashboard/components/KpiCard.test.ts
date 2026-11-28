import { describe, expect, it } from 'vitest';
import { deltaPresentation } from './KpiCard';

describe('deltaPresentation', () => {
  it('stays neutral when both periods are zero', () => {
    expect(deltaPresentation(0, 0, false)).toEqual({
      text: '0.0% vs previous',
      favorable: null,
    });
    expect(deltaPresentation(0, 0, true).favorable).toBeNull();
  });

  it('treats a new loss as unfavorable and a new refund as an increase', () => {
    expect(deltaPresentation(-10, 0, false)).toEqual({
      text: '▼ New vs previous',
      favorable: false,
    });
    expect(deltaPresentation(5, 0, false)).toEqual({
      text: '▲ New vs previous',
      favorable: true,
    });
    expect(deltaPresentation(5, 0, true)).toEqual({
      text: '▲ New vs previous',
      favorable: false,
    });
  });

  it('hides an arrow when the change rounds to 0.0%', () => {
    expect(deltaPresentation(10, 10, false)).toEqual({
      text: '0.0% vs previous',
      favorable: null,
    });
    expect(deltaPresentation(100.04, 100, false)).toEqual({
      text: '0.0% vs previous',
      favorable: null,
    });
    expect(deltaPresentation(5, 5, true).favorable).toBeNull();
  });

  it('colors a refund drop as favorable and a sales rise as favorable', () => {
    expect(deltaPresentation(5, 10, true)).toEqual({
      text: '▼ 50.0% vs previous',
      favorable: true,
    });
    expect(deltaPresentation(15, 10, false)).toEqual({
      text: '▲ 50.0% vs previous',
      favorable: true,
    });
    expect(deltaPresentation(15, 10, true).favorable).toBe(false);
  });
});