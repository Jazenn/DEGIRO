import { neonTargetsStore } from './targets';
import { createApplication } from './application';
import { neonSnapshotStore } from './snapshot-store';
export default { fetch: createApplication({ targets: env => neonTargetsStore(env.DATABASE_URL), readAccepted: env => neonSnapshotStore(env.DATABASE_URL).readAccepted() }) };

