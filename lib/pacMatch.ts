/** Join site candidates to FEC PAC rows. Does not read or rewrite filing extracts. */

export type PacQuery = {
  scope: "federal" | "hi-state";
  state: string;
  office: string;
  district: string;
  name: string;
  /** Tie-break only when several crosswalk rows share this name. Never the PAC join key. */
  siteCandidateId?: string;
  cscRegNo?: string | null;
};

export type CrosswalkRow = {
  site_name?: string | null;
  state?: string | null;
  office?: string | null;
  district?: string | null;
  site_name_variants?: string[] | null;
  cand_id?: string | null;
  possible_cand_ids?: string | string[] | null;
  match_method?: string | null;
  match_confidence?: string | null;
  fec_name?: string | null;
};

type Summary = {
  total: number;
  count: number;
  givers?: number;
  support_total?: number;
  oppose_total?: number;
  support_count?: number;
  oppose_count?: number;
};

export type PacTxn = {
  giver_name?: string | null;
  amount?: number | null;
  date?: string | null;
  source_url?: string | null;
  support_oppose?: string | null;
};

export type PacRecord = {
  candidate_id?: string | null;
  candidate_name?: string | null;
  fec_candidate_url?: string | null;
  data_as_of?: string | null;
  source_url?: string | null;
  summary?: {
    pac_contributions?: Summary;
    outside_spending?: Summary;
    party_coordinated?: Summary;
  } | null;
  pac_contributions?: PacTxn[] | null;
  outside_spending?: PacTxn[] | null;
  party_coordinated?: PacTxn[] | null;
};

export type PacStateFile = {
  data_as_of?: string;
  sources?: Record<string, { url?: string } | string>;
  by_candidate?: Record<string, PacRecord>;
  hawaii_state_by_candidate?: Record<string, PacRecord>;
};

export const AMBIGUOUS_NOTE =
  "More than one FEC registration matches this name; each is shown separately.";
export const UNCONFIRMED_NOTE = "Unconfirmed FEC match";
export const PANEL_NOTE =
  "From FEC filings (federal) and Hawaii Campaign Spending Commission (state). Communication costs by corporations/unions are listed under outside spending.";

export function notFoundText(dataAsOf: string): string {
  return `Not found in FEC candidate filings as of ${dataAsOf}.`;
}

export function noneReportedText(dataAsOf: string): string {
  return `None reported as of ${dataAsOf}`;
}

export function combinesText(ids: string[]): string {
  return `Combines FEC IDs ${ids.join(", ")} (duplicate registrations of the same candidate).`;
}

export function parsePossibleIds(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw.map((id) => String(id).trim()).filter(Boolean);
  }
  if (typeof raw !== "string" || !raw.trim()) return [];
  return raw
    .split(/[;,]/)
    .map((id) => id.trim())
    .filter(Boolean);
}

type ParsedRow = {
  index: number;
  state: string;
  office: string;
  district: string;
  siteName: string;
  names: string[];
  candId: string | null;
  possible: string[];
  rejected: boolean;
  confidence: string;
  method: string;
};

export type PacIndex = {
  rows: ParsedRow[];
  byName: Map<string, number[]>;
  /** Confirmed same-person id sets, keyed by every member id. Order is cand_id then possible ids. */
  canonical: Map<string, string[]>;
};

function clean(value: string | null | undefined): string {
  return (value || "").trim();
}

function nameKey(state: string, office: string, district: string, name: string): string {
  return `${state}|${office}|${district}|${name}`;
}

export function buildIndex(rows: CrosswalkRow[]): PacIndex {
  const parsed: ParsedRow[] = rows.map((row, index) => {
    const method = clean(row.match_method);
    const rejected = method === "review_unmatch";
    const possible = rejected ? [] : parsePossibleIds(row.possible_cand_ids);
    const names = new Set<string>();
    const siteName = clean(row.site_name);
    if (siteName) names.add(siteName);
    for (const variant of row.site_name_variants || []) {
      const v = clean(variant);
      if (v) names.add(v);
    }
    const fecName = clean(row.fec_name);
    if (fecName) names.add(fecName);
    return {
      index,
      state: clean(row.state),
      office: clean(row.office),
      district: clean(row.district),
      siteName,
      names: [...names],
      candId: clean(row.cand_id) || null,
      possible,
      rejected,
      confidence: clean(row.match_confidence),
      method,
    };
  });

  const byName = new Map<string, number[]>();
  for (const row of parsed) {
    for (const name of row.names) {
      const key = nameKey(row.state, row.office, row.district, name);
      const list = byName.get(key);
      if (list) list.push(row.index);
      else byName.set(key, [row.index]);
    }
  }

  const canonical = new Map<string, string[]>();
  for (const row of parsed) {
    if (!row.candId || row.possible.length === 0) continue;
    const ids = [row.candId, ...row.possible.filter((id) => id !== row.candId)];
    let list: string[] | undefined;
    for (const id of ids) {
      const existing = canonical.get(id);
      if (existing) {
        list = existing;
        break;
      }
    }
    if (!list) list = [];
    for (const id of ids) {
      if (!list.includes(id)) list.push(id);
    }
    for (const id of list) canonical.set(id, list);
  }

  return { rows: parsed, byName, canonical };
}

export type FederalMatch =
  | { kind: "hidden" }
  | { kind: "not-found" }
  | { kind: "ambiguous"; ids: string[] }
  | { kind: "matched"; ids: string[]; unconfirmed: boolean; rowIndexes: number[] };

function officesFor(query: PacQuery): string[] {
  if (query.state === "VI" && (query.office === "U.S. House" || query.office === "U.S. House (Delegate)")) {
    return ["U.S. House (Delegate)", "U.S. House"];
  }
  return [query.office];
}

function expandIds(index: PacIndex, row: ParsedRow): string[] {
  if (!row.candId) return [];
  return index.canonical.get(row.candId) || [row.candId];
}

export function matchFederal(index: PacIndex, query: PacQuery): FederalMatch {
  const hits: ParsedRow[] = [];
  const seen = new Set<number>();
  for (const office of officesFor(query)) {
    const key = nameKey(query.state, office, query.district, query.name);
    for (const rowIndex of index.byName.get(key) || []) {
      if (seen.has(rowIndex)) continue;
      seen.add(rowIndex);
      hits.push(index.rows[rowIndex]);
    }
  }
  if (hits.length === 0) return { kind: "hidden" };

  let chosen = hits;
  if (chosen.length > 1 && query.siteCandidateId) {
    const id = query.siteCandidateId;
    const tied = chosen.filter(
      (row) => row.candId === id || row.possible.includes(id) || expandIds(index, row).includes(id),
    );
    if (tied.length === 1) chosen = tied;
  }
  if (chosen.length > 1) {
    const signatures = chosen.map((row) => expandIds(index, row).join(","));
    if (signatures[0] && signatures.every((sig) => sig === signatures[0])) {
      const named = chosen.find((row) => row.siteName);
      chosen = [named || chosen[0]];
    } else {
      return { kind: "hidden" };
    }
  }

  const row = chosen[0];
  if (row.rejected || (!row.candId && row.possible.length === 0)) {
    return { kind: "not-found" };
  }
  if (!row.candId && row.possible.length > 0) {
    return { kind: "ambiguous", ids: row.possible };
  }
  if (!row.candId) return { kind: "not-found" };
  const ids = expandIds(index, row);
  return {
    kind: "matched",
    ids,
    unconfirmed: row.confidence === "medium",
    rowIndexes: [row.index],
  };
}

export type MoneyRow = {
  giverName: string;
  amount: number;
  date: string | null;
  sourceUrl: string;
  supportOppose: "support" | "oppose" | null;
};

export type GiverGroup = {
  name: string;
  total: number;
  rows: MoneyRow[];
};

export type SectionModel = {
  key: "pac_contributions" | "outside_spending" | "party_coordinated";
  title: string;
  total: number;
  count: number;
  supportTotal: number | null;
  opposeTotal: number | null;
  dataAsOf: string;
  sourceUrl: string;
  givers: GiverGroup[];
};

export type PanelModel =
  | { kind: "hidden" }
  | { kind: "pending" }
  | { kind: "unavailable" }
  | { kind: "not-found"; dataAsOf: string; sourceUrl: string }
  | {
      kind: "ambiguous";
      blocks: { id: string; fecUrl: string | null; missing: boolean; sections: SectionModel[] }[];
    }
  | {
      kind: "matched";
      unconfirmed: boolean;
      combinesNote: string | null;
      fecLinks: { id: string; url: string }[];
      sections: SectionModel[];
    };

const SECTIONS: { key: SectionModel["key"]; title: string; outside: boolean }[] = [
  { key: "pac_contributions", title: "PAC contributions", outside: false },
  { key: "outside_spending", title: "Outside spending", outside: true },
  { key: "party_coordinated", title: "Party coordinated spending", outside: false },
];

function fileSource(file: PacStateFile | undefined): string {
  const pas = file?.sources?.["pas226.zip"];
  if (pas && typeof pas === "object" && pas.url) return pas.url;
  if (typeof pas === "string") return pas;
  return "";
}

function supportOf(value: string | null | undefined): "support" | "oppose" | null {
  if (value === "support" || value === "oppose") return value;
  return null;
}

export function groupGivers(rows: MoneyRow[]): GiverGroup[] {
  const order: string[] = [];
  const grouped = new Map<string, MoneyRow[]>();
  for (const row of rows) {
    const name = row.giverName || "Giver name not listed";
    const list = grouped.get(name);
    if (list) list.push(row);
    else {
      grouped.set(name, [row]);
      order.push(name);
    }
  }
  const groups = order.map((name) => {
    const list = (grouped.get(name) || []).slice().sort((a, b) => {
      const date = (b.date || "").localeCompare(a.date || "");
      if (date) return date;
      return b.amount - a.amount;
    });
    const total = list.reduce((sum, row) => sum + row.amount, 0);
    return { name, total, rows: list };
  });
  groups.sort((a, b) => b.total - a.total || a.name.localeCompare(b.name));
  return groups;
}

function sectionFromRecords(key: SectionModel["key"], title: string, outside: boolean, records: PacRecord[], fallbackAsOf: string, fallbackSource: string): SectionModel {
  let total = 0;
  let count = 0;
  let supportTotal = 0;
  let opposeTotal = 0;
  let sawOutside = false;
  const txns: MoneyRow[] = [];
  let dataAsOf = fallbackAsOf;
  let sourceUrl = fallbackSource;
  for (const rec of records) {
    if (rec.data_as_of) dataAsOf = rec.data_as_of;
    if (rec.source_url) sourceUrl = rec.source_url;
    const summary = rec.summary?.[key];
    if (summary) {
      total += summary.total || 0;
      count += summary.count || 0;
      if (outside) {
        sawOutside = true;
        supportTotal += summary.support_total || 0;
        opposeTotal += summary.oppose_total || 0;
      }
    }
    for (const row of rec[key] || []) {
      txns.push({
        giverName: clean(row.giver_name),
        amount: typeof row.amount === "number" ? row.amount : 0,
        date: clean(row.date) || null,
        sourceUrl: clean(row.source_url),
        supportOppose: supportOf(row.support_oppose),
      });
    }
  }
  return {
    key,
    title,
    total,
    count,
    supportTotal: outside && sawOutside ? supportTotal : null,
    opposeTotal: outside && sawOutside ? opposeTotal : null,
    dataAsOf,
    sourceUrl,
    givers: groupGivers(txns),
  };
}

function sectionsFor(records: PacRecord[], file: PacStateFile | undefined): SectionModel[] {
  const fallbackAsOf = clean(file?.data_as_of);
  const fallbackSource = fileSource(file);
  return SECTIONS.map((section) =>
    sectionFromRecords(section.key, section.title, section.outside, records, fallbackAsOf, fallbackSource),
  );
}

function lookupRecord(file: PacStateFile, id: string, hiState: boolean): PacRecord | undefined {
  if (hiState) return file.hawaii_state_by_candidate?.[id];
  return file.by_candidate?.[id];
}

function fecLinks(records: PacRecord[], ids: string[]): { id: string; url: string }[] {
  const links: { id: string; url: string }[] = [];
  ids.forEach((id, i) => {
    const url = clean(records[i]?.fec_candidate_url);
    if (url) links.push({ id, url });
  });
  return links;
}

type Prelim =
  | { kind: "hidden" }
  | { kind: "not-found" }
  | { kind: "ambiguous"; ids: string[] }
  | { kind: "matched"; ids: string[]; unconfirmed: boolean; hiState: boolean };

function prelimFor(index: PacIndex, query: PacQuery | null, file: PacStateFile | undefined): Prelim {
  if (!query || (query.scope === "federal" && !query.name.trim())) return { kind: "hidden" };
  if (query.scope === "hi-state") {
    if (!file) return { kind: "matched", ids: [], unconfirmed: false, hiState: true };
    const table = file.hawaii_state_by_candidate || {};
    if (query.cscRegNo) {
      return table[query.cscRegNo]
        ? { kind: "matched", ids: [query.cscRegNo], unconfirmed: false, hiState: true }
        : { kind: "hidden" };
    }
    const hits = Object.entries(table).filter(([, rec]) => clean(rec.candidate_name) === query.name);
    if (hits.length === 1) return { kind: "matched", ids: [hits[0][0]], unconfirmed: false, hiState: true };
    return { kind: "hidden" };
  }
  const match = matchFederal(index, query);
  if (match.kind === "hidden") return { kind: "hidden" };
  if (match.kind === "not-found") return { kind: "not-found" };
  if (match.kind === "ambiguous") return { kind: "ambiguous", ids: match.ids };
  return { kind: "matched", ids: match.ids, unconfirmed: match.unconfirmed, hiState: false };
}

export function decideAll(
  queries: (PacQuery | null)[],
  index: PacIndex,
  files: Record<string, PacStateFile | undefined>,
): PanelModel[] {
  const prelims = queries.map((query) => {
    const file = query ? files[query.state] : undefined;
    if (query && !file) {
      if (query.scope === "hi-state" || matchFederal(index, query).kind !== "hidden") {
        return { kind: "pending" as const };
      }
    }
    return prelimFor(index, query, file);
  });

  const owner = new Map<string, number>();
  prelims.forEach((prelim, i) => {
    if (prelim.kind !== "matched" || prelim.ids.length === 0) return;
    const key = `matched:${[...prelim.ids].sort().join(",")}`;
    const current = owner.get(key);
    const name = clean(queries[i]?.name);
    if (current == null) {
      owner.set(key, i);
      return;
    }
    const currentName = clean(queries[current]?.name);
    if (!currentName && name) owner.set(key, i);
  });

  return prelims.map((prelim, i) => {
    if (prelim.kind === "pending") return { kind: "pending" };
    if (prelim.kind === "hidden") return { kind: "hidden" };
    const query = queries[i];
    const file = query ? files[query.state] : undefined;
    if (!file || !query) return { kind: "pending" };
    if (prelim.kind === "not-found") {
      return { kind: "not-found", dataAsOf: clean(file.data_as_of), sourceUrl: fileSource(file) };
    }
    if (prelim.kind === "ambiguous") {
      return {
        kind: "ambiguous",
        blocks: prelim.ids.map((id) => {
          const rec = lookupRecord(file, id, false);
          return {
            id,
            fecUrl: clean(rec?.fec_candidate_url) || null,
            missing: !rec,
            sections: sectionsFor(rec ? [rec] : [], file),
          };
        }),
      };
    }
    const key = `matched:${[...prelim.ids].sort().join(",")}`;
    if (owner.get(key) !== i) return { kind: "hidden" };
    const records = prelim.ids.map((id) => lookupRecord(file, id, prelim.hiState)).filter((rec): rec is PacRecord => !!rec);
    if (records.length === 0) {
      return { kind: "not-found", dataAsOf: clean(file.data_as_of), sourceUrl: fileSource(file) };
    }
    const aligned = prelim.ids.map((id) => lookupRecord(file, id, prelim.hiState));
    return {
      kind: "matched",
      unconfirmed: prelim.unconfirmed,
      combinesNote: prelim.ids.length > 1 ? combinesText(prelim.ids) : null,
      fecLinks: fecLinks(
        aligned.map((rec) => rec || {}),
        prelim.ids,
      ),
      sections: sectionsFor(records, file),
    };
  });
}

export function countCrosswalkPanels(rows: CrosswalkRow[]): {
  matched: number;
  ambiguous: number;
  notInFec: number;
} {
  let matched = 0;
  let ambiguous = 0;
  let notInFec = 0;
  for (const row of rows) {
    const candId = clean(row.cand_id);
    const method = clean(row.match_method);
    const possible = method === "review_unmatch" ? [] : parsePossibleIds(row.possible_cand_ids);
    if (method === "review_unmatch" || (!candId && possible.length === 0)) notInFec += 1;
    else if (!candId && possible.length > 0) ambiguous += 1;
    else matched += 1;
  }
  return { matched, ambiguous, notInFec };
}
