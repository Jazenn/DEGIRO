"""Public-provider adapters. No source facts are fabricated or silently defaulted."""
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
import csv
import io
import json
import re
from urllib.parse import urlparse

from backend.exposure import validate_fund

# Public fund/source identity verified from the official product page. This does
# not assert that the owner's broker holds this fund; a manifest is still required.
ISHARES_HOLDINGS = {
    'IE00B4K48X80': 'https://www.ishares.com/uk/individual/en/products/251861/ishares-core-msci-europe-ucits-etf-eur-acc/latest-holdings.csv',
}


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


def parse_ishares_holdings(text, source_url, retrieved_at):
    rows = [row for row in csv.reader(io.StringIO(text.lstrip('\ufeff'))) if row]
    if len(rows) < 3 or len(rows[0]) != 2 or rows[0][0] != 'Fund Holdings as of':
        raise ValueError('Dated iShares holdings header unavailable')
    as_of = datetime.strptime(rows[0][1], '%d/%b/%Y').date().isoformat()
    header = ['Ticker', 'Name', 'Sector', 'Asset Class', 'Market Value', 'Weight (%)',
              'Notional Value', 'Shares', 'Price', 'Location', 'Exchange', 'Market Currency']
    if rows[1] != header or any(len(row) != len(header) for row in rows[2:]):
        raise ValueError('Unsupported iShares holdings columns')
    holdings = []
    for row in rows[2:]:
        item = dict(zip(header, row))
        if not re.fullmatch(r'\d+(?:\.\d+)?', item['Weight (%)']):
            raise ValueError('Unsupported iShares weight')
        holdings.append({'name': item['Name'], 'security_id': None,
                         'weight_pct': item['Weight (%)'],
                         'country': item['Location'] if item['Location'] not in ('', '-') else None,
                         'sector': item['Sector'] if item['Sector'] not in ('', '-') else None})
    result = {'as_of': as_of, 'retrieved_at': retrieved_at, 'source_url': source_url,
              'provider': 'iShares', 'identifier_namespace': None, 'complete': False,
              'country_basis': 'ishares_reported_location', 'sector_taxonomy': None,
              'weight_basis': 'provider_reported_market_value', 'holdings': holdings}
    validate_fund(result)
    return result


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
        elif config['adapter'] in ('vanguard-page', 'ishares-csv'):
            url = config['url']
            parsed = urlparse(url)
            ishares = config['adapter'] == 'ishares-csv'
            if ishares:
                approved = fund_id in ISHARES_HOLDINGS and url == ISHARES_HOLDINGS[fund_id]
            else:
                approved = parsed.scheme == 'https' and parsed.hostname == 'www.vanguard.co.uk' and parsed.path.startswith('/professional/product/etf/')
            if not approved:
                raise ValueError('Unapproved official source URL')
            with requests.get(url, timeout=20, stream=True, allow_redirects=False) as response:
                response.raise_for_status()
                media_type = response.headers.get('Content-Type', '').split(';')[0].strip().lower()
                if response.status_code != 200 or media_type not in (('text/plain', 'text/csv') if ishares else ('text/html',)):
                    raise ValueError('Provider source response unavailable')
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > 2 * 1024 * 1024:
                        raise ValueError('Provider page too large')
                    chunks.append(chunk)
            text = b''.join(chunks).decode('utf-8')
            retrieved = datetime.now(timezone.utc).isoformat()
            if ishares:
                source = parse_ishares_holdings(text, url, retrieved)
            else:
                if not re.fullmatch(r'[A-Z]{2}[A-Z0-9]{9}[0-9]', fund_id) or fund_id not in text:
                    raise ValueError('Official page does not identify the requested fund')
                source = parse_vanguard_holdings(text, url, retrieved)
        else:
            raise ValueError('Unsupported ETF exposure adapter')
        validate_fund(source)
        sources[fund_id] = source
    return sources
