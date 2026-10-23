import { createRefresh } from './refresh';
import { neonRefreshStore } from './valuation-store';
import { fetchQuote } from './quote-provider';
import { neonTargetsStore } from './targets';
import { handleImports } from './import-store';
import { createApplication } from './application';
import { neonSnapshotStore } from './snapshot-store';
export default { fetch: createApplication({
  refresh: env => createRefresh(neonRefreshStore(env.DATABASE_URL), fetchQuote)(),
  handleImports,
  targets: env => neonTargetsStore(env.DATABASE_URL),
  readAccepted: env => neonSnapshotStore(env.DATABASE_URL).readAccepted(),
}) };
