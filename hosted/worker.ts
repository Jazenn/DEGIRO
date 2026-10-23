import { createApplication } from './application';
import { neonSnapshotStore } from './snapshot-store';
export default { fetch: createApplication({ readAccepted: env => neonSnapshotStore(env.DATABASE_URL).readAccepted() }) };
