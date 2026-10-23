import { neonTargetsStore } from './targets';
import { handleImports } from './import-store';
import { createApplication } from './application';
import { neonSnapshotStore } from './snapshot-store';
export default { fetch: createApplication({ handleImports, targets: env => neonTargetsStore(env.DATABASE_URL), readAccepted: env => neonSnapshotStore(env.DATABASE_URL).readAccepted() }) };

