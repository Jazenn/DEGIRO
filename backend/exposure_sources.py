"""Public-provider adapters. No source facts are fabricated or silently defaulted."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import json
import re
from urllib.parse import urlparse

from backend.exposure import validate_fund


class Tables(HTMLParser):
    def __init__(self):
        super().__init__()
        self.context = ''
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.table = {'context': self.context[-2000:], 'rows': []}
        elif tag == 'tr' and self.table is not None:
            self.row = []
        elif tag in ('td', 'th') and self.row is not None:
            self.cell = ''

    def handle_data(self, data):
        self.context = (self.context + ' ' + data)[-4000:]
        if self.cell is not None:
            self.cell += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.cell is not None:
            self.row.append(' '.join(self.cell.split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            self.table['rows'].append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None


def parse_vanguard_holdings(html, source_url, retrieved_at):
    parser = Tables()
    parser.feed(html)
    for table in parser.tables:
        rows = table['rows']
        if not rows or rows[0][:4] != ['Holding name', '% of market value', 'Sector', 'Region']:
            continue
        dates = re.findall(r'As at\s+(\d{1,2}\s+[A-Za-z]+\s+\d{4})', table['context'], re.I)
        if not dates:
            raise ValueError('Holdings source date missing')
        as_of = datetime.strptime(dates[-1].replace('Sept', 'Sep'), '%d %b %Y').date().isoformat()
        holdings = []
        for row in rows[1:]:
            if len(row) < 4 or not re.fullmatch(r'\d+(?:\.\d+)?%', row[1]):
                raise ValueError('Unsupported provider holdings row')
            holdings.append({'name': row[0], 'security_id': None, 'weight_pct': row[1][:-1],
                             'sector': row[2] or None, 'country': row[3] or None})
        result = {'as_of': as_of, 'retrieved_at': retrieved_at, 'source_url': source_url,
                  'provider': 'Vanguard', 'identifier_namespace': None, 'complete': False,
                  'country_basis': 'provider_reported_region', 'sector_taxonomy': None,
                  'weight_basis': 'provider_reported_market_value', 'holdings': holdings}
        validate_fund(result)
        return result
    raise ValueError('Dated Vanguard holdings table unavailable; previous data retained')


def load_sources(manifest_path):
    """Manifest explicitly maps broker fund IDs to reviewed source configurations.

    An official provider page or a normalized dated JSON file is required. There
    is no synthetic/default source and no guessing fund identity from a name.
    """
    import requests
    path = Path(manifest_path)
    sources = {}
    for fund_id, config in json.loads(path.read_text(encoding='utf-8')).items():
        if config['adapter'] == 'normalized-json':
            source = json.loads((path.parent / config['path']).read_text(encoding='utf-8'))
            if source.get('fund_id') != fund_id:
                raise ValueError('Reviewed source fund identity does not match manifest')
        elif config['adapter'] == 'vanguard-page':
            url = config['url']
            parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname != 'www.vanguard.co.uk' or not parsed.path.startswith('/professional/product/etf/'):
                raise ValueError('Unapproved official source URL')
            with requests.get(url, timeout=20, stream=True, allow_redirects=False) as response:
                response.raise_for_status()
                if response.status_code != 200 or 'text/html' not in response.headers.get('Content-Type', ''):
                    raise ValueError('Provider source response unavailable')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise ValueError('Provider page too large')
                    chunks.append(chunk)
            html = b''.join(chunks).decode('utf-8')
            if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', fund_id) or fund_id not in html:
                raise ValueError('Official page does not identify the requested fund')
            source = parse_vanguard_holdings(html, url,
                                            datetime.now(timezone.utc).isoformat())
        else:
            raise ValueError('Unsupported ETF exposure adapter')
        validate_fund(source)
        sources[fund_id] = source
    return sources
