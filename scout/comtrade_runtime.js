const BASE_URL = 'https://comtradeapi.un.org/public/v1/preview/C/A/HS';
const DEFAULT_QUERY = Object.freeze({
  reporterCode: 204,
  period: 2024,
  cmdCode: '2501',
  flowCode: 'M',
  partnerCode: 0,
  partner2Code: 0,
  maxRecords: 500
});

export async function acquireComtrade(overrides = {}) {
  const query = { ...DEFAULT_QUERY, ...overrides };
  const params = new URLSearchParams({
    reporterCode: String(query.reporterCode),
    period: String(query.period),
    cmdCode: query.cmdCode,
    flowCode: query.flowCode,
    partnerCode: String(query.partnerCode),
    partner2Code: String(query.partner2Code),
    maxRecords: String(query.maxRecords)
  });

  const url = BASE_URL + '?' + params.toString();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const response = await fetch(url, {
      headers: {
        Accept: 'application/json',
        'User-Agent': 'ALAGBARA-SCOUT-WEB-02C/0.2'
      },
      cache: 'no-store',
      signal: controller.signal
    });

    if (!response.ok) {
      throw new Error('UN Comtrade acquisition failed: HTTP ' + response.status);
    }

    const payload = await response.json();

    if (!payload || !Array.isArray(payload.data)) {
      throw new Error('UN Comtrade returned an invalid payload: data[] missing');
    }

    return {
      acquired_at: new Date().toISOString(),
      source: 'UN Comtrade',
      source_type: 'OFFICIAL_TRADE_STATISTICS',
      source_url: url,
      query: {
        reporter: query.reporterCode,
        period: query.period,
        hs: query.cmdCode,
        flow: query.flowCode,
        partner: query.partnerCode,
        partner2: query.partner2Code
      },
      payload
    };
  } catch (error) {
    if (error?.name === 'AbortError') {
      throw new Error('UN Comtrade acquisition timed out after 15 seconds');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export function comtradeToKernelRecords(envelope) {
  return envelope.payload.data.map(row => {
    const quantityKg = row.netWgt == null ? null : Number(row.netWgt);
    const tradeValue = row.primaryValue == null ? null : Number(row.primaryValue);

    return {
      source: envelope.source,
      source_type: envelope.source_type,
      retrieved_at: envelope.acquired_at,
      confidence: 'HIGH',
      provenance: {
        source_url: envelope.source_url,
        query: envelope.query
      },
      raw_record: row,
      observations: {
        reporter: row.reporterDesc ?? null,
        partner: row.partnerDesc ?? null,
        period: row.refYear ?? envelope.query.period,
        flow: row.flowDesc ?? 'Import',
        quantity: {
          value: quantityKg == null ? null : quantityKg / 1000,
          unit: 't',
          source_field: 'netWgt',
          estimated: Boolean(row.isNetWgtEstimated)
        },
        trade_value: {
          value: tradeValue,
          unit: 'USD',
          source_field: 'primaryValue'
        },
        product: {
          hs_code: row.cmdCode ?? envelope.query.hs,
          classification: 'aggregate'
        },
        attributes: {
          graph_subject: row.reporterDesc ?? 'UNKNOWN',
          graph_object: row.partnerDesc ?? 'UNKNOWN',
          graph_predicate: 'IMPORTED_FROM'
        }
      }
    };
  });
}
