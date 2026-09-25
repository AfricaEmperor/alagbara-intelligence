export const saltKernelInput = [
  {
    source: 'WITS / UN Comtrade', source_type: 'OFFICIAL_TRADE_STATISTICS',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'HIGH',
    provenance: { query: 'Benin imports HS 250100 from Ghana, 2024' },
    raw_record: { reporter: 'Benin', partner: 'Ghana', year: 2024, flow: 'Import', hs_code: '250100', net_wgt_kg: 5667070 },
    observations: {
      reporter: 'Benin', partner: 'Ghana', period: '2024', flow: 'Import',
      quantity: { value: 5667.07, unit: 't' }, trade_value: { value: 212000, unit: 'USD' },
      product: { hs_code: '250100', classification: 'aggregate' },
      attributes: { graph_subject: 'BENIN', graph_object: 'GHANA', graph_predicate: 'IMPORTED_FROM' }
    }
  },
  {
    source: 'Ghana mirror / UN Comtrade', source_type: 'OFFICIAL_TRADE_STATISTICS_MIRROR',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'HIGH',
    provenance: { query: 'Ghana exports HS 250100 to Benin, 2024' },
    raw_record: { reporter: 'Ghana', partner: 'Benin', year: 2024, flow: 'Export', hs_code: '250100', net_wgt_kg: 144600 },
    observations: {
      reporter: 'Ghana', partner: 'Benin', period: '2024', flow: 'Export',
      quantity: { value: 144.6, unit: 't' }, trade_value: { value: 760500, unit: 'USD' },
      product: { hs_code: '250100', classification: 'aggregate' },
      attributes: { graph_subject: 'BENIN', graph_object: 'GHANA', graph_predicate: 'IMPORTED_FROM' }
    }
  },
  {
    source: 'WITS / UN Comtrade', source_type: 'OFFICIAL_TRADE_STATISTICS',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'HIGH',
    provenance: { query: 'Benin imports HS 250100 from Senegal, 2024' },
    raw_record: { reporter: 'Benin', partner: 'Senegal', year: 2024, flow: 'Import', hs_code: '250100', net_wgt_kg: 19992400 },
    observations: {
      reporter: 'Benin', partner: 'Senegal', period: '2024', flow: 'Import',
      quantity: { value: 19992.4, unit: 't' }, trade_value: { value: 2605000, unit: 'USD' },
      product: { hs_code: '250100', classification: 'aggregate' },
      attributes: { graph_subject: 'BENIN', graph_object: 'SENEGAL', graph_predicate: 'IMPORTED_FROM' }
    }
  },
  {
    source: 'WITS / UN Comtrade', source_type: 'OFFICIAL_TRADE_STATISTICS',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'HIGH',
    provenance: { query: 'Benin imports HS 250100 from Egypt, 2024' },
    raw_record: { reporter: 'Benin', partner: 'Egypt', year: 2024, flow: 'Import', hs_code: '250100', net_wgt_kg: 14909100 },
    observations: {
      reporter: 'Benin', partner: 'Egypt', period: '2024', flow: 'Import',
      quantity: { value: 14909.1, unit: 't' }, trade_value: { value: 1160000, unit: 'USD' },
      product: { hs_code: '250100', classification: 'aggregate' },
      attributes: { graph_subject: 'BENIN', graph_object: 'EGYPT', graph_predicate: 'IMPORTED_FROM' }
    }
  },
  {
    source: 'WITS / UN Comtrade', source_type: 'OFFICIAL_TRADE_STATISTICS',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'HIGH',
    provenance: { query: 'Benin imports HS 250100 from India, 2024' },
    raw_record: { reporter: 'Benin', partner: 'India', year: 2024, flow: 'Import', hs_code: '250100', net_wgt_kg: 9404160 },
    observations: {
      reporter: 'Benin', partner: 'India', period: '2024', flow: 'Import',
      quantity: { value: 9404.16, unit: 't' }, trade_value: { value: 935000, unit: 'USD' },
      product: { hs_code: '250100', classification: 'aggregate' },
      attributes: { graph_subject: 'BENIN', graph_object: 'INDIA', graph_predicate: 'IMPORTED_FROM' }
    }
  },
  {
    source: 'TradeImeX', source_type: 'TRANSACTION_TRADE_RECORD',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'MEDIUM',
    provenance: { query: 'Regency Salt Ghana to Benin 31 Jan 2024' },
    raw_record: { date: '2024-01-31', exporter: 'Regency Salt Limited', importer: 'Louisa Djossou', origin: 'Ghana', destination: 'Benin', quantity_t: 100, packaging: '4000 x 25kg', product: 'Refined iodized salt', hs_code: '2501002000' },
    observations: {
      reporter: 'Transaction record', partner: 'Benin', period: '2024-01-31', flow: 'Export',
      exporter: 'Regency Salt Limited', importer: 'Louisa Djossou', origin: 'Ghana', destination: 'Benin',
      entry_point: 'Aflao Customs Border Post', quantity: { value: 100, unit: 't' },
      trade_value: { value: 20648.10, unit: 'USD', basis: 'CIF' },
      product: { hs_code: '2501002000', description: 'Refined iodized salt', packaging: '4000 x 25kg' },
      attributes: { graph_subject: 'Regency Salt Limited', graph_object: 'Louisa Djossou', graph_predicate: 'SUPPLIED' }
    }
  },
  {
    source: 'Volza', source_type: 'TRANSACTION_TRADE_RECORD',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'MEDIUM',
    provenance: { query: 'Regency Salt Ghana to Benin 17 May 2024' },
    raw_record: { date: '2024-05-17', exporter: 'Regency Salt Limited', importer: 'UNKNOWN', origin: 'Ghana', destination: 'Benin', quantity_t: 100, packaging: '4000 x 25kg', product: 'Refined iodized salt', hs_code: '2501002000' },
    observations: {
      reporter: 'Transaction record', partner: 'Benin', period: '2024-05-17', flow: 'Export',
      exporter: 'Regency Salt Limited', importer: 'UNKNOWN', origin: 'Ghana', destination: 'Benin',
      quantity: { value: 100, unit: 't' },
      trade_value: { value: 16707.695, unit: 'USD', basis: 'UNSPECIFIED' },
      product: { hs_code: '2501002000', description: 'Refined iodized salt', packaging: '4000 x 25kg' },
      attributes: { graph_subject: 'Regency Salt Limited', graph_object: 'UNKNOWN_IMPORTER', graph_predicate: 'SUPPLIED' }
    }
  },
  {
    source: 'Volza', source_type: 'TRANSACTION_TRADE_RECORD',
    retrieved_at: '2026-09-25T00:00:00Z', confidence: 'MEDIUM',
    provenance: { query: 'India to Benin 23 Mar 2024' },
    raw_record: { date: '2024-03-23', exporter: 'UNKNOWN_EXPORTER', importer: 'UNKNOWN_IMPORTER', origin: 'India', destination: 'Benin', quantity_t: 140, packaging: '25kg bags', product: 'Edible powdered iodised salt', hs_code: '250100' },
    observations: {
      reporter: 'Transaction record', partner: 'Benin', period: '2024-03-23', flow: 'Export',
      exporter: 'UNKNOWN_EXPORTER', importer: 'UNKNOWN_IMPORTER', origin: 'India', destination: 'Benin',
      quantity: { value: 140, unit: 't' }, trade_value: { value: null, unit: 'USD' },
      product: { hs_code: '250100', description: 'Edible powdered iodised salt', packaging: '25kg bags' },
      attributes: { graph_subject: 'UNKNOWN_EXPORTER', graph_object: 'UNKNOWN_IMPORTER', graph_predicate: 'SUPPLIED' }
    }
  }
];