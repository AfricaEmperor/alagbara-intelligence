const jsonValue = (raw) => {
  const value = raw.trim();
  try { return JSON.parse(value); }
  catch { return value.replace(/^\"|\"$/g, ''); }
};

export function parseAIL(source) {
  const lines = String(source || '').split(/\r?\n/).map(x => x.trim()).filter(Boolean);
  const statements = [];
  const errors = [];

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    try {
      let m;
      if ((m = line.match(/^OBSERVE\s+(\S+)\s*=\s*(.+?)\s+@\s+(EV-\d{3})$/))) {
        statements.push({ type: 'OBSERVE', subject: m[1], value: jsonValue(m[2]), evidence_id: m[3] });
        continue;
      }
      if ((m = line.match(/^UNKNOWN\s+(\S+)$/))) {
        statements.push({ type: 'UNKNOWN', subject: m[1] });
        continue;
      }
      if ((m = line.match(/^DERIVE\s+(CL-\d{3})\s+(\S+)\s*=\s*(.+?)\s+FROM\s+((?:CL-\d{3})(?:\s*,\s*CL-\d{3})*)$/))) {
        statements.push({ type: 'DERIVE', id: m[1], subject: m[2], value: jsonValue(m[3]), from: m[4].split(/\s*,\s*/) });
        continue;
      }
      if ((m = line.match(/^RELATE\s+(ED-\d{3})\s+(\S+)\s+-\[([^\]]+)\]->\s+(\S+)\s+@\s+(EV-\d{3})$/))) {
        statements.push({ type: 'RELATE', id: m[1], from: m[2], predicate: m[3], to: m[4], evidence_id: m[5] });
        continue;
      }
      if ((m = line.match(/^DECIDE\s+(ACT-\d{3})\s+(.+)$/))) {
        statements.push({ type: 'DECIDE', id: m[1], intent: m[2].trim() });
        continue;
      }
      if ((m = line.match(/^AUTHORIZE\s+(ACT-\d{3})\s+BY\s+(\S+)$/))) {
        statements.push({ type: 'AUTHORIZE', action_id: m[1], principal: m[2] });
        continue;
      }
      if ((m = line.match(/^EXECUTE\s+(ACT-\d{3})\s+RESULT\s+(.+)$/))) {
        statements.push({ type: 'EXECUTE', action_id: m[1], result: m[2].trim() });
        continue;
      }
      errors.push({ line: i + 1, message: 'Unrecognized AIL statement' });
    } catch (error) {
      errors.push({ line: i + 1, message: error.message });
    }
  }

  return { ok: errors.length === 0, statements, errors };
}

export function validateAILProgram(program) {
  const errors = [...(program.errors || [])];
  const evidenceIds = new Set();
  const claimIds = new Set();
  const actionStates = new Map();

  for (const stmt of program.statements || []) {
    if (stmt.type === 'OBSERVE') evidenceIds.add(stmt.evidence_id);
    if (stmt.type === 'DERIVE') claimIds.add(stmt.id);
  }

  for (const stmt of program.statements || []) {
    if (stmt.type === 'DERIVE') {
      for (const source of stmt.from) if (!claimIds.has(source) && source !== 'CL-001') errors.push({ message: 'DERIVE references unknown claim ' + source });
    }
    if (stmt.type === 'RELATE' && !evidenceIds.has(stmt.evidence_id)) errors.push({ message: 'RELATE violates NO EDGE WITHOUT PROVENANCE: ' + stmt.evidence_id });
    if (stmt.type === 'AUTHORIZE') {
      actionStates.set(stmt.action_id, { authorized: true, principal: stmt.principal });
    }
    if (stmt.type === 'EXECUTE') {
      if (!actionStates.get(stmt.action_id)?.authorized) errors.push({ message: 'EXECUTE requires prior AUTHORIZE for ' + stmt.action_id });
      actionStates.set(stmt.action_id, { ...(actionStates.get(stmt.action_id) || {}), executed: true, result: stmt.result });
    }
  }

  return { ok: errors.length === 0, errors };
}