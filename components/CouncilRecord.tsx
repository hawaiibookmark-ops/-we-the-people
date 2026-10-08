"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { dataUrl } from "@/lib/config";

// Official Clerk text only. No vote tallies, rates, or for/against labels.

const PAGE_SIZE = 50;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type Roll = { recorded?: string | null } | null;

type Reading = {
  measure?: string;
  reading_date?: string | null;
  close_date?: string | null;
  actions_as_recorded?: string[] | null;
  enriques_vote?: string | null;
  ayes?: Roll;
  noes?: Roll;
  absent?: Roll;
  excused?: Roll;
  introducer?: string | null;
  title_as_written?: string | null;
  title_note?: string | null;
  flags?: string[] | null;
  source_url?: string | null;
  record_source?: string | null;
};

type Seat = {
  committee?: string;
  enriques_role?: string;
  from?: string;
  to?: string;
  designated_by?: string;
  source_url?: string;
};

type Withdrawn = {
  measure?: string;
  status_as_recorded?: string;
  note?: string | null;
  source_url?: string;
};

type ReadingsFile = {
  minutes?: string;
  term_as_recorded?: {
    start?: string;
    end?: string;
    source?: string;
    source_url?: string;
  };
  readings?: Reading[];
};

type CommitteesFile = {
  seats?: Seat[];
  withdrawn?: Withdrawn[];
};

type HonestEmptyFile = {
  status?: string;
  source_url?: string;
};

type CandidateEntry = {
  window?: string;
  readings?: string;
  committees?: string;
  honest_empty?: string;
};

type CouncilIndex = {
  races?: Record<string, { candidates?: Record<string, CandidateEntry> }>;
};

type RecordPayload = {
  kind: "record";
  readings: ReadingsFile;
  committees: CommitteesFile | null;
};

type EmptyPayload = {
  kind: "empty";
  file: HonestEmptyFile;
};

const jsonCache = new Map<string, Promise<unknown>>();

function loadJson<T>(file: string): Promise<T> {
  const url = dataUrl(file);
  let pending = jsonCache.get(url) as Promise<T> | undefined;
  if (!pending) {
    pending = fetch(url).then((res) => {
      if (!res.ok) throw new Error(`${file} ${res.status}`);
      return res.json() as Promise<T>;
    });
    jsonCache.set(url, pending);
    pending.catch(() => {
      jsonCache.delete(url);
    });
  }
  return pending;
}

function councilFile(name: string): string {
  if (!/^[A-Za-z0-9._-]+$/.test(name)) throw new Error("bad council record path");
  return `council-record/${name}`;
}

function formatIso(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!match) return iso;
  const month = MONTHS[Number(match[2]) - 1];
  if (!month) return iso;
  return `${month} ${Number(match[3])}, ${match[1]}`;
}

function formatWindow(window: string): string {
  const match = /^(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})$/.exec(window.trim());
  if (!match) return `(${window})`;
  return `(${formatIso(match[1])} – ${formatIso(match[2])})`;
}

function recorded(block: Roll): string {
  if (!block || typeof block !== "object") return "";
  return block.recorded ?? "";
}

function readingDate(row: Reading): string {
  if (row.reading_date == null) return row.close_date || "";
  return row.reading_date;
}

function actionsText(actions: string[] | null | undefined): string {
  return (actions || []).join("\n");
}

function sectionTitle(entry: CandidateEntry): string {
  const windowLabel = entry.window ? formatWindow(entry.window) : "";
  return windowLabel ? `Official County Council record ${windowLabel}` : "Official County Council record";
}

function SourceLink({ href, children }: { href?: string | null; children: string }) {
  if (!href) return null;
  return (
    <a href={href} rel="noreferrer">
      {children}
    </a>
  );
}

function ReadingsTable({ readings }: { readings: Reading[] }) {
  const filterId = useId();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return readings;
    return readings.filter((row) => {
      const measure = (row.measure || "").toLowerCase();
      const title = (row.title_as_written || "").toLowerCase();
      return measure.includes(needle) || title.includes(needle);
    });
  }, [readings, query]);
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const slice = filtered.slice(safePage * PAGE_SIZE, safePage * PAGE_SIZE + PAGE_SIZE);

  return (
    <div>
      <label className="src" htmlFor={filterId}>
        Filter by measure or title
      </label>
      <div>
        <input
          id={filterId}
          className="council-filter"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setPage(0);
          }}
          type="search"
        />
      </div>
      {filtered.length === 0 ? <p className="src">No measures or titles match that text.</p> : null}
      {slice.length > 0 ? (
        <div className="council-record-table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Measure</th>
                <th scope="col">Date</th>
                <th scope="col">Actions as recorded</th>
                <th scope="col">Vote</th>
                <th scope="col">Record</th>
              </tr>
            </thead>
            <tbody>
              {slice.map((row, index) => (
                <tr key={`${safePage}-${index}`}>
                  <td>
                    {row.measure || ""}
                    {row.record_source ? <div className="src">{row.record_source}</div> : null}
                  </td>
                  <td>{readingDate(row)}</td>
                  <td className="council-actions">{actionsText(row.actions_as_recorded)}</td>
                  <td className="council-vote">{row.enriques_vote || ""}</td>
                  <td>
                    <details className="council-reading">
                      <summary>Recorded roll call</summary>
                      {row.record_source ? <p>record_source: {row.record_source}</p> : null}
                      <p>Ayes: {recorded(row.ayes ?? null)}</p>
                      <p>Noes: {recorded(row.noes ?? null)}</p>
                      <p>Absent: {recorded(row.absent ?? null)}</p>
                      <p>Excused: {recorded(row.excused ?? null)}</p>
                      <p>Introducer: {row.introducer || ""}</p>
                      {row.title_as_written ? <p className="council-title">{row.title_as_written}</p> : null}
                      {row.title_note ? <p className="council-caption">OCR text from the Clerk scan</p> : null}
                      {(row.flags || []).map((flag, flagIndex) => (
                        <p className="src" key={flagIndex}>
                          {flag}
                        </p>
                      ))}
                      <p className="src">
                        <SourceLink href={row.source_url}>Clerk record</SourceLink>
                      </p>
                    </details>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {pageCount > 1 ? (
        <div className="council-pager">
          <button type="button" onClick={() => setPage(safePage - 1)} disabled={safePage === 0}>
            Previous
          </button>
          <span className="src">
            Page {safePage + 1} of {pageCount}
          </span>
          <button type="button" onClick={() => setPage(safePage + 1)} disabled={safePage >= pageCount - 1}>
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}

function RecordBody({ payload }: { payload: RecordPayload }) {
  const term = payload.readings.term_as_recorded;
  const seats = payload.committees?.seats || [];
  const withdrawn = payload.committees?.withdrawn || [];
  return (
    <div>
      {seats.length > 0 ? (
        <div className="council-record-table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Committee</th>
                <th scope="col">Role</th>
                <th scope="col">From–to</th>
                <th scope="col">Designated by</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {seats.map((seat, index) => (
                <tr key={`${seat.committee || ""}-${seat.from || ""}-${index}`}>
                  <td>{seat.committee || ""}</td>
                  <td>{seat.enriques_role || ""}</td>
                  <td>
                    {seat.from || ""}
                    {seat.from || seat.to ? " – " : ""}
                    {seat.to || ""}
                  </td>
                  <td>{seat.designated_by || ""}</td>
                  <td>
                    <SourceLink href={seat.source_url}>Source</SourceLink>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {withdrawn.map((item, index) => (
        <p className="src" key={`withdrawn-${index}`}>
          {[item.measure, item.status_as_recorded, item.note].filter(Boolean).join(" ")}{" "}
          <SourceLink href={item.source_url}>Source</SourceLink>
        </p>
      ))}
      {payload.readings.minutes ? <p className="src">{payload.readings.minutes}</p> : null}
      {term ? (
        <p className="src">
          {[term.start, term.end].filter(Boolean).join(" – ")}
          {term.source ? `. ${term.source}` : ""} <SourceLink href={term.source_url}>Source</SourceLink>
        </p>
      ) : null}
      <ReadingsTable readings={payload.readings.readings || []} />
    </div>
  );
}

export function CouncilRecord({ office, name }: { office: string; name: string }) {
  const [entry, setEntry] = useState<CandidateEntry | null | undefined>(undefined);
  const [phase, setPhase] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [payload, setPayload] = useState<RecordPayload | EmptyPayload | null>(null);
  const started = useRef(false);

  useEffect(() => {
    let cancelled = false;
    loadJson<CouncilIndex>("council-record/index.json")
      .then((index) => {
        if (cancelled) return;
        setEntry(index.races?.[office]?.candidates?.[name] ?? null);
      })
      .catch(() => {
        if (!cancelled) setEntry(null);
      });
    return () => {
      cancelled = true;
    };
  }, [office, name]);

  function ensureLoaded() {
    if (!entry || started.current) return;
    started.current = true;
    setPhase("loading");
    const job = (async () => {
      if (entry.honest_empty) {
        const file = await loadJson<HonestEmptyFile>(councilFile(entry.honest_empty));
        return { kind: "empty", file } as EmptyPayload;
      }
      const readingsName = entry.readings;
      if (!readingsName) throw new Error("missing readings");
      const [readings, committees] = await Promise.all([
        loadJson<ReadingsFile>(councilFile(readingsName)),
        entry.committees ? loadJson<CommitteesFile>(councilFile(entry.committees)) : Promise.resolve(null),
      ]);
      return { kind: "record", readings, committees } as RecordPayload;
    })();
    job
      .then((next) => {
        setPayload(next);
        setPhase("ready");
      })
      .catch(() => {
        started.current = false;
        setPhase("error");
      });
  }

  if (!entry) return null;
  const title = sectionTitle(entry);

  return (
    <details
      className="council-record"
      onToggle={(event) => {
        if (event.currentTarget.open) ensureLoaded();
      }}
    >
      <summary>{title}</summary>
      {phase === "loading" || phase === "idle" ? <p className="src">Loading official record…</p> : null}
      {phase === "error" ? (
        <p className="src">
          The Clerk record could not be loaded.{" "}
          <button type="button" className="council-retry" onClick={() => ensureLoaded()}>
            Try again
          </button>
        </p>
      ) : null}
      {phase === "ready" && payload?.kind === "empty" ? (
        <p className="src">
          {payload.file.status || ""} <SourceLink href={payload.file.source_url}>Source</SourceLink>
        </p>
      ) : null}
      {phase === "ready" && payload?.kind === "record" ? <RecordBody payload={payload} /> : null}
    </details>
  );
}
