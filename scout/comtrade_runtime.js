const BASE_URL = 'https://comtradeapi.un.org/public/v1/preview/C/A/HS';

export async function acquireComtrade({
  reporterCode = 204,
  period = 2024,
  cmdCode = '2501',
  flowCode = 'M',
  partnerCode = 0,
  partner2Code = 0,
  maxRecords = 500
} = {}) {
  const params = new URLSearchParams({
    reporterCode: String(reporterCode),
    period: String(period),
    cmdCode,
    flowCode,
    partnerCode: String(partnerCode),
    partner2Code: String(partner2Code),
    maxRecords: String(maxRecords)
  });

  const url = BASE_URL + '?' + params.toString();
  const response = await fetch(url, {
    headers: { 'User-Agent': 'ALAGBARA-SCOUT-WEB-02C/0.1' },
    cache: 'no-store'
  });

  if (!response.ok) {
    throw new Error('UN Comtrade acquisition failed: HTTP ' + response.status);
  }

  const payload = await response.json();

  return {
    acquired_at: new Date().toISOString(),
    source: 'UN Comtrade',
    source_type: 'OFFICIAL_TRADE_STATISTICS',
    source_url: url,
    query: {
      reporter: reporterCode,
      period,
      hs: cmdCode,
      flow: flowCode,
      partner: partnerCode,
      partner2: partner2Code
    },
    payload
  };
}

function rows(envelope) {
  const data = envelope?.payload?.data;
  return Array.isArray(data) ? data : [];
}

export function comtradeToKernelRecords(envelope) {
  return rows(envelope).map(row => ({
    source: 'UN Comtrade',
    source_type: 'OFFICIAL_TRADE_STATISTICS',
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
        value: row.netWgt == null ? null : Number(row.netWgt) / 1000,
        unit: 't'
      },
      trade_value: {
        value: row.primaryValue ?? null,
        unit: 'USD'
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
  }));
}
