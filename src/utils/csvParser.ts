/**
 * Interface representing a normalized parsed transaction record.
 */
export interface ParsedTransaction {
  date: string;
  time: string;
  product: string;
  isin: string;
  description: string;
  quantity: number | null;
  price: number | null;
  value: number | null;
  amount: number | null;
  balance: number | null;
  orderId: string;
  rowHash: string;
}

export interface CsvParseResult {
  success: boolean;
  rowsProcessed: number;
  newRows: number;
  duplicatesSkipped: number;
  errors: string[];
  transactions: ParsedTransaction[];
}

export interface ParseOptions {
  existingHashes?: string[] | Set<string>;
}

const HEADER_ALIASES: Record<string, string[]> = {
  date: ['date', 'datum', 'transaction date', 'date of transaction'],
  time: ['time', 'tijd', 'transaction time'],
  product: ['product', 'productnaam', 'name', 'fonds', 'security'],
  isin: ['isin', 'isin code', 'isin / ticker'],
  quantity: ['quantity', 'aantal'],
  price: ['price', 'koers', 'unit price'],
  value: [
    'value',
    'waarde',
    'waarde eur',
    'value eur',
    'lokale waarde',
    'local value',
    'waarde in lokale valuta',
    'value in local currency',
  ],
  amount: ['amount', 'mutatie', 'change'],
  balance: ['balance', 'saldo'],
  description: ['description', 'omschrijving'],
  order_id: ['order_id', 'order id', 'orderid'],
};

/**
 * Splits a CSV line into cells respecting quoted commas/semicolons.
 */
function parseCsvLine(line: string, delimiter: string): string[] {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++; // skip escaped quote
      } else {
        inQuotes = !inQuotes;
      }
    } else if (char === delimiter && !inQuotes) {
      result.push(current.trim());
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current.trim());
  return result;
}

/**
 * Detects delimiter (semicolon, comma, tab) from the first line.
 */
function detectDelimiter(firstLine: string): string {
  const semicolonCount = (firstLine.match(/;/g) || []).length;
  const commaCount = (firstLine.match(/,/g) || []).length;
  const tabCount = (firstLine.match(/\t/g) || []).length;

  if (semicolonCount >= commaCount && semicolonCount >= tabCount && semicolonCount > 0) {
    return ';';
  }
  if (commaCount >= semicolonCount && commaCount >= tabCount && commaCount > 0) {
    return ',';
  }
  if (tabCount > 0) {
    return '\t';
  }
  return ',';
}

/**
 * Simple fast deterministic hash for a string (compatible across all runtimes).
 */
function computeDeterministicHash(str: string): string {
  let hash1 = 0x811c9dc5;
  let hash2 = 0x517cc1b7;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    hash1 ^= ch;
    hash1 = Math.imul(hash1, 0x01000193);
    hash2 ^= ch;
    hash2 = Math.imul(hash2, 0x01000193);
  }
  return (
    ('00000000' + (hash1 >>> 0).toString(16)).slice(-8) +
    ('00000000' + (hash2 >>> 0).toString(16)).slice(-8)
  );
}

/**
 * Generates a stable deterministic row hash.
 */
function generateRowHash(row: {
  date: string;
  time: string;
  isin: string;
  orderId: string;
  amount: number | null;
  value: number | null;
}): string {
  const payload = [
    row.date || '',
    row.time || '',
    row.isin || '',
    row.orderId || '',
    row.amount !== null && row.amount !== undefined ? String(row.amount) : '',
    row.value !== null && row.value !== undefined ? String(row.value) : '',
  ].join('|');
  return computeDeterministicHash(payload);
}

/**
 * Normalizes European formatted number strings (e.g., "1.234,56" or "-1205,00" or "120.50").
 */
function parseNumber(value: string | undefined): number | null {
  if (!value) return null;
  const clean = value.replace(/[\s€$£]/g, '').trim();
  if (!clean) return null;

  // If comma is used as decimal separator (e.g. 1.205,50 or 1205,50)
  if (clean.includes(',') && !clean.includes('.')) {
    const num = parseFloat(clean.replace(',', '.'));
    return isNaN(num) ? null : num;
  }
  if (clean.includes('.') && clean.includes(',')) {
    if (clean.lastIndexOf(',') > clean.lastIndexOf('.')) {
      // European 1.250,50 -> 1250.50
      const num = parseFloat(clean.replace(/\./g, '').replace(',', '.'));
      return isNaN(num) ? null : num;
    } else {
      // Standard 1,250.50 -> 1250.50
      const num = parseFloat(clean.replace(/,/g, ''));
      return isNaN(num) ? null : num;
    }
  }

  const num = parseFloat(clean);
  return isNaN(num) ? null : num;
}

/**
 * Parses and validates DEGIRO CSV exports (Dutch or English Account.csv / Transactions.csv).
 */
export function parseDegiroCsv(
  csvContent: string,
  options: ParseOptions = {}
): CsvParseResult {
  if (!csvContent || !csvContent.trim()) {
    return {
      success: false,
      rowsProcessed: 0,
      newRows: 0,
      duplicatesSkipped: 0,
      errors: ['CSV content is empty'],
      transactions: [],
    };
  }

  const lines = csvContent
    .replace(/\r\n/g, '\n')
    .replace(/\r/g, '\n')
    .split('\n')
    .filter((l) => l.trim().length > 0);

  if (lines.length < 2) {
    return {
      success: false,
      rowsProcessed: 0,
      newRows: 0,
      duplicatesSkipped: 0,
      errors: ['Unsupported DEGIRO CSV format: file contains no transaction rows'],
      transactions: [],
    };
  }

  const delimiter = detectDelimiter(lines[0]);
  const rawHeaders = parseCsvLine(lines[0], delimiter).map((h) =>
    h.toLowerCase().replace(/^\ufeff/, '').trim()
  );

  // Map header positions to canonical field keys
  const headerMap: Record<string, number> = {};
  for (let i = 0; i < rawHeaders.length; i++) {
    const h = rawHeaders[i];
    for (const [canonical, aliases] of Object.entries(HEADER_ALIASES)) {
      if (aliases.includes(h)) {
        headerMap[canonical] = i;
        break;
      }
    }
  }

  // Validate minimum required headers
  const available = new Set(Object.keys(headerMap));
  const hasDate = available.has('date');
  const hasProductOrDescription = available.has('product') || available.has('description');
  const hasFinancialMetric =
    available.has('value') ||
    available.has('amount') ||
    available.has('quantity') ||
    available.has('price');

  if (!hasDate || !hasProductOrDescription || !hasFinancialMetric) {
    return {
      success: false,
      rowsProcessed: 0,
      newRows: 0,
      duplicatesSkipped: 0,
      errors: [
        'Unsupported DEGIRO CSV format: expected transaction columns were not found.',
      ],
      transactions: [],
    };
  }

  const seenHashes = new Set<string>();
  if (options.existingHashes) {
    for (const h of options.existingHashes) {
      seenHashes.add(h);
    }
  }

  const transactions: ParsedTransaction[] = [];
  let duplicatesSkipped = 0;
  let rowsProcessed = 0;

  for (let i = 1; i < lines.length; i++) {
    const rawLine = lines[i];
    if (!rawLine.trim()) continue;

    const cells = parseCsvLine(rawLine, delimiter);
    if (cells.length < 2 || cells.every((c) => !c.trim())) continue;

    rowsProcessed++;

    const getVal = (key: string): string =>
      headerMap[key] !== undefined && cells[headerMap[key]] !== undefined
        ? cells[headerMap[key]].trim()
        : '';

    const date = getVal('date');
    const time = getVal('time');
    const product = getVal('product');
    const isin = getVal('isin');
    const description = getVal('description');
    const orderId = getVal('order_id');
    const quantity = parseNumber(getVal('quantity'));
    const price = parseNumber(getVal('price'));
    const value = parseNumber(getVal('value'));
    const amount = parseNumber(getVal('amount'));
    const balance = parseNumber(getVal('balance'));

    const rowHash = generateRowHash({
      date,
      time,
      isin,
      orderId,
      amount,
      value: value !== null ? value : amount,
    });

    if (seenHashes.has(rowHash)) {
      duplicatesSkipped++;
      continue;
    }

    seenHashes.add(rowHash);
    transactions.push({
      date,
      time,
      product: product || description,
      isin,
      description,
      quantity,
      price,
      value: value !== null ? value : amount,
      amount,
      balance,
      orderId,
      rowHash,
    });
  }

  return {
    success: true,
    rowsProcessed,
    newRows: transactions.length,
    duplicatesSkipped,
    errors: [],
    transactions,
  };
}
