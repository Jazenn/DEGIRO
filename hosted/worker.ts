import { createContribution, neonContributionStore } from './contribution-store';
import { createRefresh, type RefreshStore } from './refresh';
import { neonRefreshStore } from './valuation-store';
import { fetchQuote } from './quote-provider';
import { neonTargetsStore } from './targets';
import { handleImports } from './import-store';
import { createApplication } from './application';
import { neonSnapshotStore } from './snapshot-store';
import type { AuthQuery } from './auth-store';
// External database/provider transports are replaceable for Worker entry tests.
export function workerApplication(options: { authQuery?: AuthQuery; refreshStore?: (url: string) => RefreshStore; quote?: typeof fetchQuote } = {}) {
  let binding: string | undefined, refresh: ReturnType<typeof createRefresh> | undefined;
  return createApplication({
    authQuery: options.authQuery,
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

