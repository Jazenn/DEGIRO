export interface TargetWeightsValidationResult {
  valid: boolean;
  sum: number;
  error?: string;
}

export interface CryptoTriggerSettingsInput {
  buy_dip_trigger?: number | null;
  sell_profit_trigger?: number | null;
  buy_budget?: number | null;
}

export interface CryptoTriggerValidationResult {
  valid: boolean;
  errors: Record<string, string>;
}

/**
 * Validates that all asset target percentages sum to exactly 100%
 * and that no target percentage is negative.
 */
export function validateTargetWeights(
  weights: Record<string, number>
): TargetWeightsValidationResult {
  const entries = Object.entries(weights);
  if (entries.length === 0) {
    return {
      valid: false,
      sum: 0,
      error: 'Portfolio must contain at least one asset.',
    };
  }

  let sum = 0;
  for (const [, weight] of entries) {
    const val = Number(weight);
    if (Number.isNaN(val) || val < 0) {
      return {
        valid: false,
        sum,
        error: 'Target percentages cannot be negative.',
      };
    }
    sum += val;
  }

  // Allow a tiny floating-point epsilon (0.01%) for rounding differences
  const isHundred = Math.abs(sum - 100) < 0.01;

  if (!isHundred) {
    return {
      valid: false,
      sum,
      error: `Total must equal 100% (currently ${sum.toFixed(1)}%).`,
    };
  }

  return {
    valid: true,
    sum,
  };
}

/**
 * Validates cryptocurrency buy dip triggers, profit-taking targets, and cash budgets.
 */
export function validateCryptoTriggerSettings(
  settings: CryptoTriggerSettingsInput
): CryptoTriggerValidationResult {
  const errors: Record<string, string> = {};

  const { buy_dip_trigger, sell_profit_trigger, buy_budget } = settings;

  if (buy_dip_trigger !== null && buy_dip_trigger !== undefined) {
    const buyVal = Number(buy_dip_trigger);
    if (Number.isNaN(buyVal) || buyVal <= 0) {
      errors.buy_dip_trigger = 'Buy dip trigger must be greater than zero.';
    }
  }

  if (sell_profit_trigger !== null && sell_profit_trigger !== undefined) {
    const sellVal = Number(sell_profit_trigger);
    if (Number.isNaN(sellVal) || sellVal <= 0) {
      errors.sell_profit_trigger = 'Profit target must be greater than zero.';
    }
  }

  if (buy_budget !== null && buy_budget !== undefined) {
    const budgetVal = Number(buy_budget);
    if (Number.isNaN(budgetVal) || budgetVal < 0) {
      errors.buy_budget = 'Buy budget cannot be negative.';
    }
  }

  if (
    buy_dip_trigger !== null &&
    buy_dip_trigger !== undefined &&
    sell_profit_trigger !== null &&
    sell_profit_trigger !== undefined
  ) {
    const buyVal = Number(buy_dip_trigger);
    const sellVal = Number(sell_profit_trigger);
    if (!Number.isNaN(buyVal) && !Number.isNaN(sellVal) && buyVal >= sellVal) {
      errors.buy_dip_trigger = 'Buy dip trigger must be lower than profit target.';
    }
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}
