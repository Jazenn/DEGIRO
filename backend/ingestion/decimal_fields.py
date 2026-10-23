"""Exact economic fields from preserved broker text, before any legacy float path."""
from decimal import Decimal, localcontext
import re


def source_number(value):
    text = str(value).strip().replace(' ', '')
    if text.rfind(',') > text.rfind('.'):
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '')
    result = Decimal(text)
    if not result.is_finite():
        raise ValueError('Non-finite source amount')
    return result


def canonical_decimal(value):
    # Decimal.normalize() itself obeys the current precision and can truncate.
    text = format(value, 'f')
    return '0' if value.is_zero() else text.rstrip('0').rstrip('.') if '.' in text else text


def economic_fields(record, source_format):
    source = record.get('source_record') or {}
    kind = record['type']
    amount = source_number(record['amount'])
    quantity = source_number(record['quantity']).copy_abs()
    price = source_number(record['price'])
    if source_format == 'account':
        for key in ('mutatie', 'change', 'amount'):
            if key in source:
                keys = list(source)
                value = source[key]
                if str(value).isalpha():
                    value = source[keys[keys.index(key)+1]]
                amount = source_number(value) if value else Decimal(0)
                break
        if kind in ('BUY', 'SELL'):
            match = re.search(r'(?:Koop|Verkoop|Buy|Sell)\s+([0-9.,]+)\s*@\s*([0-9.,]+)', record['description'], re.I)
            if not match:
                raise ValueError('Missing exact execution values')
            quantity, price = source_number(match[1]).copy_abs(), source_number(match[2])
    elif source_format == 'transactions':
        amount_names = ('transactiekosten en/of kosten van derden eur', 'transaction costs', 'fee') if kind == 'FEE' else (
            'waarde eur', 'value eur', 'waarde', 'value', 'lokale waarde', 'waarde in lokale valuta', 'local value', 'value in local currency')
        for key in amount_names:
            if source.get(key):
                value = source_number(source[key]).copy_abs()
                amount = value.copy_negate() if kind in ('BUY', 'FEE') else value
                break
        if kind in ('BUY', 'SELL'):
            for key in ('koers', 'price'):
                if source.get(key):
                    price = source_number(source[key])
                    break
            raw_quantity = next((source[key] for key in ('aantal', 'quantity') if source.get(key)), None)
            if raw_quantity and not source_number(raw_quantity).is_zero():
                quantity = source_number(raw_quantity).copy_abs()
            else:
                with localcontext() as context:
                    context.prec = 80
                    quantity = amount.copy_abs() / price
    return {key: canonical_decimal(value) for key, value in (('amount', amount), ('quantity', quantity), ('price', price))}
