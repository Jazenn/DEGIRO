import { createContribution, neonContributionStore } from './contribution-store';
import { cryptoExecutions, neonExecutionStore } from './crypto-execution-store';
import { previewStageReview, neonStageReviewReader } from './crypto-stage-store';
import { neonCryptoPlans } from './crypto-plan-store';
import { previewCryptoLevels, neonCryptoMarketReader } from './crypto-market-store';
import { createRefresh, type RefreshStore } from './refresh';
import { neonRefreshStore } from './valuation-store';
import { fetchQuote } from './quote-provider';
import { neonTargetsStore } from './targets';
import { handleImports } from './import-store';
import { createApplication } from './application';
import { neonSnapshotStore } from './snapshot-store';
import type { AuthQuery } from './auth-store';
import { neonHistoryStore } from './history-store';
// External database/provider transports are replaceable for Worker entry tests.
export function workerApplication(options: { authQuery?: AuthQuery; refreshStore?: (url: string) => RefreshStore; quote?: typeof fetchQuote } = {}) {
  let binding: string | undefined, refresh: ReturnType<typeof createRefresh> | undefined;
  return createApplication({
    authQuery: options.authQuery,
    readHistory: (value, env, signal) => neonHistoryStore(env.DATABASE_URL).read(value, signal),
    cryptoExecutions: (method, value, env) => cryptoExecutions(neonExecutionStore(env.DATABASE_URL))(method, value),
    cryptoStageReview: (value, env) => previewStageReview(value, neonStageReviewReader(env.DATABASE_URL)),
    cryptoPlans: (method, value, env) => neonCryptoPlans(env.DATABASE_URL)(method, value),
    cryptoLevels: (value, env) => previewCryptoLevels(value, neonCryptoMarketReader(env.DATABASE_URL)),
    refresh: env => {
      if (!refresh || binding !== env.DATABASE_URL) {
        binding = env.DATABASE_URL;
        refresh = createRefresh((options.refreshStore ?? neonRefreshStore)(binding), options.quote ?? fetchQuote);
      }
      return refresh();
    },
    contribution: (value, env) => createContribution(neonContributionStore(env.DATABASE_URL))(value),
    handleImports,
    targets: env => neonTargetsStore(env.DATABASE_URL),
    readAccepted: env => neonSnapshotStore(env.DATABASE_URL).readAccepted(),
  });
}
export default { fetch: workerApplication() };

