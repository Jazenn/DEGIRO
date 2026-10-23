"""Publish reviewed dated ETF sources onto one coherent accepted generation.

Requires explicit publisher DATABASE_URL and ETF_EXPOSURE_MANIFEST JSON. No
private records are printed; a concurrent generation change causes rollback.
"""
import json
import os
import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from backend.exposure import build_exposure
from backend.exposure_sources import load_sources


def main():
    import psycopg2
    from psycopg2.extras import Json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', help='Explicit reviewed local manifest, including normalized source files')
    args = parser.parse_args()
    # Hosted runner only fetches official sources. Reviewed normalized local JSON
    # is available through load_sources for separately authorized operator runs.
    if args.manifest:
        sources = load_sources(args.manifest)
    else:
        manifest = json.loads(os.environ['ETF_EXPOSURE_MANIFEST'])
        if any(config.get('adapter') != 'vanguard-page' for config in manifest.values()):
            raise ValueError('Hosted exposure job accepts only official source adapters')
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'sources.json'
            path.write_text(json.dumps(manifest), encoding='utf-8')
            sources = load_sources(path)
    with psycopg2.connect(os.environ['DATABASE_URL']) as connection, connection.cursor() as cursor:
        cursor.execute('SELECT g.generation_id,g.data_classification,g.read_model FROM hosted_snapshot_pointer p JOIN hosted_snapshot_generations g USING(generation_id) WHERE singleton=true')
        previous = cursor.fetchone()
        if not previous:
            raise ValueError('An accepted canonical Snapshot is required')
        previous_id, classification, model = previous
        model['etf_exposure'] = build_exposure(model, sources)
        generation = str(uuid4())
        cursor.execute('INSERT INTO hosted_snapshot_generations(generation_id,data_classification,read_model) VALUES(%s,%s,%s)',
                       (generation, classification, Json(model)))
        cursor.execute('UPDATE hosted_snapshot_pointer SET generation_id=%s WHERE singleton=true AND generation_id=%s',
                       (generation, previous_id))
        if cursor.rowcount != 1:
            raise ValueError('Accepted Snapshot changed; retry against the current generation')
    print('Published dated ETF exposure on one coherent generation; no financial records printed.')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # Provider/parser/database exception strings may contain private config.
        raise SystemExit('ETF exposure publication failed; previous generation preserved. Review source availability and configuration privately.') from None
