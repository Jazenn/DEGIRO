import { describe, it, expect } from 'vitest';
import {
  validateTargetWeights,
  validateCryptoTriggerSettings,
} from './settingsValidation';

describe('settingsValidation', () => {
  describe('validateTargetWeights', () => {
    it('returns valid when target weights sum exactly to 100%', () => {
      const weights = {
        'VWCE.DE': 55.5,
        'EXUS.DE': 21.0,
        'BTC-EUR': 8.0,
        'IMAE.AS': 8.5,
        'ASWC.DE': 7.0,
      };

      const result = validateTargetWeights(weights);
      expect(result.valid).toBe(true);
      expect(result.sum).toBeCloseTo(100.0, 2);
      expect(result.error).toBeUndefined();
    });

    it('returns invalid when target weights sum to less than 100%', () => {
      const weights = {
        'VWCE.DE': 50.0,
        'BTC-EUR': 10.0,
      };

      const result = validateTargetWeights(weights);
      expect(result.valid).toBe(false);
      expect(result.sum).toBe(60.0);
      expect(result.error).toMatch(/total must equal 100%/i);
    });

    it('returns invalid when target weights sum to more than 100%', () => {
      const weights = {
        'VWCE.DE': 60.0,
        'EXUS.DE': 30.0,
        'BTC-EUR': 20.0,
      };

      const result = validateTargetWeights(weights);
      expect(result.valid).toBe(false);
      expect(result.sum).toBe(110.0);
      expect(result.error).toMatch(/total must equal 100%/i);
    });

    it('returns invalid when any weight is negative', () => {
      const weights = {
        'VWCE.DE': 105.0,
        'BTC-EUR': -5.0,
      };

      const result = validateTargetWeights(weights);
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/negative/i);
    });

    it('returns invalid when weights map is empty', () => {
      const result = validateTargetWeights({});
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/at least one asset/i);
    });
  });

  describe('validateCryptoTriggerSettings', () => {
    it('returns valid for normal buy dip trigger, sell profit target, and budget', () => {
      const result = validateCryptoTriggerSettings({
        buy_dip_trigger: 58500,
        sell_profit_trigger: 75420,
        buy_budget: 350,
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual({});
    });

    it('allows null or empty optional triggers', () => {
      const result = validateCryptoTriggerSettings({
        buy_dip_trigger: null,
        sell_profit_trigger: null,
        buy_budget: null,
      });

      expect(result.valid).toBe(true);
      expect(result.errors).toEqual({});
    });

    it('rejects non-positive buy trigger', () => {
      const result = validateCryptoTriggerSettings({
        buy_dip_trigger: -100,
      });

      expect(result.valid).toBe(false);
      expect(result.errors.buy_dip_trigger).toMatch(/greater than zero/i);
    });

    it('rejects non-positive profit target', () => {
      const result = validateCryptoTriggerSettings({
        sell_profit_trigger: 0,
      });

      expect(result.valid).toBe(false);
      expect(result.errors.sell_profit_trigger).toMatch(/greater than zero/i);
    });

    it('rejects negative budget', () => {
      const result = validateCryptoTriggerSettings({
        buy_budget: -50,
      });

      expect(result.valid).toBe(false);
      expect(result.errors.buy_budget).toMatch(/cannot be negative/i);
    });

    it('rejects buy trigger greater than or equal to profit target', () => {
      const result = validateCryptoTriggerSettings({
        buy_dip_trigger: 80000,
        sell_profit_trigger: 75000,
      });

      expect(result.valid).toBe(false);
      expect(result.errors.buy_dip_trigger).toMatch(/must be lower than profit target/i);
    });
  });
});
