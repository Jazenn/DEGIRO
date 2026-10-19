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
  csvRowId?: number;
}

export type IngestedTransaction = ParsedTransaction;

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
 * Standard RFC 1321 MD5 hash algorithm in pure TypeScript producing
 * a 32-hexadecimal-character hash.
 */
export function computeMd5Hash(str: string): string {
  function safeAdd(x: number, y: number): number {
    const lsw = (x & 0xffff) + (y & 0xffff);
    const msw = (x >> 16) + (y >> 16) + (lsw >> 16);
    return (msw << 16) | (lsw & 0xffff);
  }

  function bitRotateLeft(num: number, cnt: number): number {
    return (num << cnt) | (num >>> (32 - cnt));
  }

  function md5cmn(q: number, a: number, b: number, x: number, s: number, t: number): number {
    return safeAdd(bitRotateLeft(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b);
  }

  function md5ff(a: number, b: number, c: number, d: number, x: number, s: number, t: number): number {
    return md5cmn((b & c) | (~b & d), a, b, x, s, t);
  }

  function md5gg(a: number, b: number, c: number, d: number, x: number, s: number, t: number): number {
    return md5cmn((b & d) | (c & ~d), a, b, x, s, t);
  }

  function md5hh(a: number, b: number, c: number, d: number, x: number, s: number, t: number): number {
    return md5cmn(b ^ c ^ d, a, b, x, s, t);
  }

  function md5ii(a: number, b: number, c: number, d: number, x: number, s: number, t: number): number {
    return md5cmn(c ^ (b | ~d), a, b, x, s, t);
  }

  // UTF-8 encode string to byte array
  const utf8Bytes: number[] = [];
  for (let i = 0; i < str.length; i++) {
    let code = str.charCodeAt(i);
    if (code < 0x80) {
      utf8Bytes.push(code);
    } else if (code < 0x800) {
      utf8Bytes.push(0xc0 | (code >> 6));
      utf8Bytes.push(0x80 | (code & 0x3f));
    } else if (code < 0xd800 || code >= 0xe000) {
      utf8Bytes.push(0xe0 | (code >> 12));
      utf8Bytes.push(0x80 | ((code >> 6) & 0x3f));
      utf8Bytes.push(0x80 | (code & 0x3f));
    } else {
      i++;
      code = 0x10000 + (((code & 0x3ff) << 10) | (str.charCodeAt(i) & 0x3ff));
      utf8Bytes.push(0xf0 | (code >> 18));
      utf8Bytes.push(0x80 | ((code >> 12) & 0x3f));
      utf8Bytes.push(0x80 | ((code >> 6) & 0x3f));
      utf8Bytes.push(0x80 | (code & 0x3f));
    }
  }

  const numBytes = utf8Bytes.length;
  const numBits = numBytes * 8;
  const bin: number[] = [];

  for (let i = 0; i < numBytes; i++) {
    bin[i >> 2] |= utf8Bytes[i] << ((i % 4) * 8);
  }

  bin[numBytes >> 2] |= 0x80 << ((numBytes % 4) * 8);
  const targetLen = (((numBytes + 8) >> 6) + 1) * 16;
  while (bin.length < targetLen) {
    bin.push(0);
  }
  bin[targetLen - 2] = numBits & 0xffffffff;
  bin[targetLen - 1] = Math.floor(numBits / 0x100000000);

  let a = 0x67452301;
  let b = 0xefcdab89;
  let c = 0x98badcfe;
  let d = 0x10325476;

  for (let i = 0; i < bin.length; i += 16) {
    const olda = a;
    const oldb = b;
    const oldc = c;
    const oldd = d;

    const x0 = bin[i] || 0;
    const x1 = bin[i + 1] || 0;
    const x2 = bin[i + 2] || 0;
    const x3 = bin[i + 3] || 0;
    const x4 = bin[i + 4] || 0;
    const x5 = bin[i + 5] || 0;
    const x6 = bin[i + 6] || 0;
    const x7 = bin[i + 7] || 0;
    const x8 = bin[i + 8] || 0;
    const x9 = bin[i + 9] || 0;
    const x10 = bin[i + 10] || 0;
    const x11 = bin[i + 11] || 0;
    const x12 = bin[i + 12] || 0;
    const x13 = bin[i + 13] || 0;
    const x14 = bin[i + 14] || 0;
    const x15 = bin[i + 15] || 0;

    a = md5ff(a, b, c, d, x0, 7, -680876936);
    d = md5ff(d, a, b, c, x1, 12, -389564586);
    c = md5ff(c, d, a, b, x2, 17, 606105819);
    b = md5ff(b, c, d, a, x3, 22, -1044525330);
    a = md5ff(a, b, c, d, x4, 7, -176418897);
    d = md5ff(d, a, b, c, x5, 12, 1200080426);
    c = md5ff(c, d, a, b, x6, 17, -1473231341);
    b = md5ff(b, c, d, a, x7, 22, -45705983);
    a = md5ff(a, b, c, d, x8, 7, 1770035416);
    d = md5ff(d, a, b, c, x9, 12, -1958414417);
    c = md5ff(c, d, a, b, x10, 17, -42063);
    b = md5ff(b, c, d, a, x11, 22, -1990404162);
    a = md5ff(a, b, c, d, x12, 7, 1804603682);
    d = md5ff(d, a, b, c, x13, 12, -40341101);
    c = md5ff(c, d, a, b, x14, 17, -1502002290);
    b = md5ff(b, c, d, a, x15, 22, 1236535329);

    a = md5gg(a, b, c, d, x1, 5, -165796510);
    d = md5gg(d, a, b, c, x6, 9, -1069501632);
    c = md5gg(c, d, a, b, x11, 14, 643717713);
    b = md5gg(b, c, d, a, x0, 20, -373897302);
    a = md5gg(a, b, c, d, x5, 5, -701558691);
    d = md5gg(d, a, b, c, x10, 9, 38016083);
    c = md5gg(c, d, a, b, x15, 14, -660478335);
    b = md5gg(b, c, d, a, x4, 20, -405537848);
    a = md5gg(a, b, c, d, x9, 5, 568446438);
    d = md5gg(d, a, b, c, x14, 9, -1019803690);
    c = md5gg(c, d, a, b, x3, 14, -187363961);
    b = md5gg(b, c, d, a, x8, 20, 1163531501);
    a = md5gg(a, b, c, d, x13, 5, -1444681467);
    d = md5gg(d, a, b, c, x2, 9, -51403784);
    c = md5gg(c, d, a, b, x7, 14, 1735328473);
    b = md5gg(b, c, d, a, x12, 20, -1926607734);

    a = md5hh(a, b, c, d, x5, 4, -378558);
    d = md5hh(d, a, b, c, x8, 11, -2022574463);
    c = md5hh(c, d, a, b, x11, 16, 1839030562);
    b = md5hh(b, c, d, a, x14, 23, -35309556);
    a = md5hh(a, b, c, d, x1, 4, -1530992060);
    d = md5hh(d, a, b, c, x4, 11, 1272893353);
    c = md5hh(c, d, a, b, x7, 16, -155497632);
    b = md5hh(b, c, d, a, x10, 23, -1094730640);
    a = md5hh(a, b, c, d, x13, 4, 681279174);
    d = md5hh(d, a, b, c, x0, 11, -358537222);
    c = md5hh(c, d, a, b, x3, 16, -722521979);
    b = md5hh(b, c, d, a, x6, 23, 76029189);
    a = md5hh(a, b, c, d, x9, 4, -640364487);
    d = md5hh(d, a, b, c, x12, 11, -421815835);
    c = md5hh(c, d, a, b, x15, 16, 530742520);
    b = md5hh(b, c, d, a, x2, 23, -995338651);

    a = md5ii(a, b, c, d, x0, 6, -198630844);
    d = md5ii(d, a, b, c, x7, 10, 1126891415);
    c = md5ii(c, d, a, b, x14, 15, -1416354905);
    b = md5ii(b, c, d, a, x5, 21, -57434055);
    a = md5ii(a, b, c, d, x12, 6, 1700485571);
    d = md5ii(d, a, b, c, x3, 10, -1894986606);
    c = md5ii(c, d, a, b, x10, 15, -1051523);
    b = md5ii(b, c, d, a, x1, 21, -2054922799);
    a = md5ii(a, b, c, d, x8, 6, 1873313359);
    d = md5ii(d, a, b, c, x15, 10, -30611744);
    c = md5ii(c, d, a, b, x6, 15, -1560198380);
    b = md5ii(b, c, d, a, x13, 21, 1309151649);
    a = md5ii(a, b, c, d, x4, 6, -145523070);
    d = md5ii(d, a, b, c, x11, 10, -1120210379);
    c = md5ii(c, d, a, b, x2, 15, 718787259);
    b = md5ii(b, c, d, a, x9, 21, -343485551);

    a = safeAdd(a, olda);
    b = safeAdd(b, oldb);
    c = safeAdd(c, oldc);
    d = safeAdd(d, oldd);
  }

  function wordToHex(val: number): string {
    let s = '';
    for (let j = 0; j < 4; j++) {
      const byte = (val >> (j * 8)) & 0xff;
      s += ('0' + byte.toString(16)).slice(-2);
    }
    return s;
  }

  return (wordToHex(a) + wordToHex(b) + wordToHex(c) + wordToHex(d)).toLowerCase();
}

function stableValue(val: unknown): string {
  if (val === null || val === undefined) return '';
  return String(val).trim();
}

/**
 * Generates a stable deterministic 32-character hexadecimal MD5 row hash across
 * (date, time, isin, order_id, amount, value).
 */
export function generateRowHash(row: {
  date: string;
  time: string;
  isin: string;
  orderId: string;
  amount: number | null;
  value: number | null;
  description?: string;
}): string {
  const payload: Record<string, string> = {
    amount: stableValue(row.amount),
    date: stableValue(row.date),
    isin: stableValue(row.isin),
    order_id: stableValue(row.orderId),
    time: stableValue(row.time),
    value: stableValue(row.value),
  };
  if (row.description) {
    payload.description = stableValue(row.description);
  }
  return computeMd5Hash(JSON.stringify(payload));
}

/**
 * Normalizes European or US formatted number strings (e.g., "1.234,56" or "-1205,00" or "120.50" or "EUR 500,00").
 */
export function parseNumber(value: string | undefined | null): number | null {
  if (value === undefined || value === null) return null;
  let clean = String(value)
    .replace(/EUR|USD|GBP|CHF|JPY/gi, '')
    .replace(/[\s€$£]/g, '')
    .trim();
  if (
    !clean ||
    clean === '-' ||
    clean.toLowerCase() === 'nan' ||
    clean.toLowerCase() === 'none'
  ) {
    return null;
  }

  // Handle trailing minus e.g. "120.50-" -> "-120.50"
  if (clean.endsWith('-')) {
    clean = '-' + clean.slice(0, -1);
  }
  // Handle parentheses e.g. "(120.50)" -> "-120.50"
  if (clean.startsWith('(') && clean.endsWith(')')) {
    clean = '-' + clean.slice(1, -1);
  }

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
 * Normalizes date strings to ISO YYYY-MM-DD.
 * Converts DD-MM-YYYY or DD/MM/YYYY into YYYY-MM-DD.
 */
export function normalizeDate(dateStr: string): string {
  if (!dateStr) return '';
  const clean = dateStr.trim();
  const dmyMatch = clean.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
  if (dmyMatch) {
    const day = dmyMatch[1].padStart(2, '0');
    const month = dmyMatch[2].padStart(2, '0');
    const year = dmyMatch[3];
    return `${year}-${month}-${day}`;
  }
  const ymdMatch = clean.match(/^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$/);
  if (ymdMatch) {
    const year = ymdMatch[1];
    const month = ymdMatch[2].padStart(2, '0');
    const day = ymdMatch[3].padStart(2, '0');
    return `${year}-${month}-${day}`;
  }
  return clean;
}

/**
 * Extracts trade quantity and execution price from transaction descriptions
 * (e.g. "Koop 10 @ 100,00 EUR" or "Sell 5 @ 120.50").
 */
export function extractTradeFromDescription(description: string): {
  quantity: number | null;
  price: number | null;
  isTrade: boolean;
  isSell: boolean;
} {
  if (!description) {
    return { quantity: null, price: null, isTrade: false, isSell: false };
  }
  const match = description.match(
    /(?:Koop|Verkoop|Buy|Sell)\s+([0-9.,eE+-]+)\s*@\s*([0-9.,eE+-]+)/i
  );
  if (!match) {
    return { quantity: null, price: null, isTrade: false, isSell: false };
  }
  const isSell = /^(?:Verkoop|Sell)/i.test(match[0].trim());
  const parsedQty = parseNumber(match[1]);
  const parsedPrice = parseNumber(match[2]);

  if (parsedQty === null) {
    return { quantity: null, price: parsedPrice, isTrade: true, isSell };
  }
  const signedQty = isSell ? -Math.abs(parsedQty) : Math.abs(parsedQty);
  return {
    quantity: signedQty,
    price: parsedPrice,
    isTrade: true,
    isSell,
  };
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
    available.has('price') ||
    available.has('balance');

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

    const getNumericCell = (key: string): number | null => {
      const idx = headerMap[key];
      if (idx === undefined || idx < 0 || idx >= cells.length) {
        return null;
      }
      const direct = parseNumber(cells[idx]);
      if (direct !== null) {
        return direct;
      }
      // If cell contains currency code like EUR/USD or is empty, inspect adjacent cells
      if (idx + 1 < cells.length) {
        const nextVal = parseNumber(cells[idx + 1]);
        if (nextVal !== null) return nextVal;
      }
      if (
        idx + 2 < cells.length &&
        (!cells[idx + 1] || /^[A-Za-z]{3}$/.test(cells[idx + 1].trim()))
      ) {
        const nextVal2 = parseNumber(cells[idx + 2]);
        if (nextVal2 !== null) return nextVal2;
      }
      if (idx - 1 >= 0) {
        const prevVal = parseNumber(cells[idx - 1]);
        if (prevVal !== null) return prevVal;
      }
      return null;
    };

    const date = normalizeDate(getVal('date'));
    const time = getVal('time');
    const product = getVal('product');
    const isin = getVal('isin');
    const description = getVal('description');
    const orderId = getVal('order_id');

    let quantity = getNumericCell('quantity');
    let price = getNumericCell('price');
    let value = getNumericCell('value');
    const amount = getNumericCell('amount');
    const balance = getNumericCell('balance');

    // Extract trade details from description if quantity or price was not in dedicated columns
    const tradeInfo = extractTradeFromDescription(description);
    if (quantity === null && tradeInfo.quantity !== null) {
      quantity = tradeInfo.quantity;
    }
    if (price === null && tradeInfo.price !== null) {
      price = tradeInfo.price;
    }
    if (value === null) {
      if (amount !== null) {
        value = amount;
      } else if (quantity !== null && price !== null) {
        value = -(quantity * price);
      }
    }

    // Handle crypto trades where quantity was blank in CSV export but price and value exist
    if ((quantity === null || quantity === 0) && price && price > 0 && value) {
      const computedQty = Math.abs(value) / price;
      const descLower = description.toLowerCase();
      const isSell = descLower.includes('verkoop') || descLower.includes('sell') || value > 0;
      quantity = isSell ? -computedQty : computedQty;
    }

    const rowHash = generateRowHash({
      date,
      time,
      isin,
      orderId,
      amount: amount !== null ? amount : value,
      value: value !== null ? value : amount,
      description,
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
      amount: amount !== null ? amount : value,
      balance,
      orderId,
      rowHash,
      csvRowId: i - 1,
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
