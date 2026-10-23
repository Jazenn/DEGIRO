// READ ONLY adapter integration check, Node >=24. Never logs connection strings or financial payloads.
import { neonSnapshotStore } from './snapshot-store.ts';
const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  console.error('Set the approved synthetic staging DATABASE_URL privately. No connection attempted.');
  process.exitCode = 1;
} else try {
  const snapshot = await neonSnapshotStore(databaseUrl).readAccepted();
  if (!snapshot || snapshot.data_classification !== 'synthetic') throw Error('Expected accepted synthetic staging generation');
  console.log('PASS: Neon HTTP adapter read one complete accepted synthetic canonical Snapshot. Worker network connectivity still requires the deployed authenticated HTTP check.');
} catch {
  console.error('FAIL: approved staging Snapshot could not be verified. No credentials or payload logged.');
  process.exitCode = 1;
}
