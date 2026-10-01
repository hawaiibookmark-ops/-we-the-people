"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { dataUrl } from "@/lib/config";
import {
  AMBIGUOUS_NOTE,
  PANEL_NOTE,
  UNCONFIRMED_NOTE,
  buildIndex,
  decideAll,
  noneReportedText,
  notFoundText,
  type CrosswalkRow,
  type GiverGroup,
  type PacQuery,
  type PacStateFile,
  type PanelModel,
  type SectionModel,
} from "@/lib/pacMatch";

const TOP_GIVERS = 25;

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
  }
  return pending;
}

function money(n: number): string {
  const negative = n < 0;
  const abs = Math.abs(n);
  const cents = Math.round(abs * 100) % 100 !== 0;
  const body = abs.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: cents ? 2 : 0,
    maximumFractionDigits: 2,
  });
  return negative ? `-${body}` : body;
}

function supportLabel(value: "support" | "oppose" | null): string {
  if (value === "support") return "Support";
  if (value === "oppose") return "Oppose";
  return "";
}

function GiverList({ givers }: { givers: GiverGroup[] }) {
  const [open, setOpen] = useState(false);
  const shown = open ? givers : givers.slice(0, TOP_GIVERS);
  return (
    <>
      {shown.map((giver) => (
        <div key={giver.name}>
          <p className="src">
            {giver.name} · {money(giver.total)} · {giver.rows.length}
          </p>
          <ul className="donor-list">
            {giver.rows.map((row, i) => {
              const text = [
                money(row.amount),
                row.date || "",
                supportLabel(row.supportOppose),
              ]
                .filter(Boolean)
                .join(" · ");
              return (
                <li key={`${giver.name}-${row.date || ""}-${row.amount}-${i}`}>
                  {row.sourceUrl ? (
                    <a href={row.sourceUrl} rel="noreferrer">
                      {text}
                    </a>
                  ) : (
                    text
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {givers.length > TOP_GIVERS && (
        <button type="button" className="pac-toggle" onClick={() => setOpen((v) => !v)}>
          {open ? "Show top 25" : "Show all"}
        </button>
      )}
    </>
  );
}

function SectionBlock({ section }: { section: SectionModel }) {
  if (section.count === 0) {
    return (
      <div>
        <p className="src">{section.title}</p>
        <p className="src">
          {noneReportedText(section.dataAsOf)}
          {section.sourceUrl ? (
            <>
              {" "}
              <a href={section.sourceUrl} rel="noreferrer">
                Source
              </a>
            </>
          ) : null}
        </p>
      </div>
    );
  }
  return (
    <div>
      <p className="src">
        {section.title} · {money(section.total)} · {section.count.toLocaleString("en-US")}
        {section.supportTotal != null && section.opposeTotal != null
          ? ` · Support ${money(section.supportTotal)} · Oppose ${money(section.opposeTotal)}`
          : ""}
      </p>
      <GiverList givers={section.givers} />
    </div>
  );
}

function PanelBody({ model }: { model: PanelModel }) {
  if (model.kind === "hidden") return null;
  if (model.kind === "pending") return <p className="src">Loading PAC filings.</p>;
  if (model.kind === "unavailable") return <p className="src">PAC filings could not be loaded.</p>;
  if (model.kind === "not-found") {
    return (
      <div className="pac">
        <p className="src">PAC and outside money</p>
        <p className="src">
          {notFoundText(model.dataAsOf)}
          {model.sourceUrl ? (
            <>
              {" "}
              <a href={model.sourceUrl} rel="noreferrer">
                Source
              </a>
            </>
          ) : null}
        </p>
        <p className="src">{PANEL_NOTE}</p>
      </div>
    );
  }
  if (model.kind === "ambiguous") {
    return (
      <div className="pac">
        <p className="src">PAC and outside money</p>
        <p className="src">{AMBIGUOUS_NOTE}</p>
        {model.blocks.map((block) => (
          <div key={block.id}>
            <p className="src">
              FEC ID {block.id}:
              {block.fecUrl ? (
                <>
                  {" "}
                  <a href={block.fecUrl} rel="noreferrer">
                    FEC candidate
                  </a>
                </>
              ) : null}
            </p>
            {block.missing ? (
              <p className="src">{notFoundText(block.sections[0]?.dataAsOf || "")}</p>
            ) : (
              block.sections.map((section) => <SectionBlock key={section.key} section={section} />)
            )}
          </div>
        ))}
        <p className="src">{PANEL_NOTE}</p>
      </div>
    );
  }
  return (
    <div className="pac">
      <p className="src">PAC and outside money</p>
      {model.unconfirmed ? <p className="src">{UNCONFIRMED_NOTE}</p> : null}
      {model.combinesNote ? <p className="src">{model.combinesNote}</p> : null}
      {model.fecLinks.length > 0 && (
        <p className="src">
          {model.fecLinks.map((link, i) => (
            <span key={link.id}>
              {i > 0 ? " · " : ""}
              <a href={link.url} rel="noreferrer">
                FEC candidate {link.id}
              </a>
            </span>
          ))}
        </p>
      )}
      {model.sections.map((section) => (
        <SectionBlock key={section.key} section={section} />
      ))}
      <p className="src">{PANEL_NOTE}</p>
    </div>
  );
}

export function PacPanels({
  queries,
  render,
}: {
  queries: (PacQuery | null)[];
  render: (panelAt: (index: number) => ReactNode) => ReactNode;
}) {
  const [crosswalk, setCrosswalk] = useState<CrosswalkRow[] | null>(null);
  const [files, setFiles] = useState<Record<string, PacStateFile>>({});
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancel = false;
    loadJson<{ rows: CrosswalkRow[] }>("pac/crosswalk.json")
      .then((data) => {
        if (!cancel) setCrosswalk(data.rows || []);
      })
      .catch(() => {
        if (!cancel) setFailed(true);
      });
    return () => {
      cancel = true;
    };
  }, []);

  const statesKey = useMemo(() => {
    const states = new Set<string>();
    for (const query of queries) {
      if (query?.state && /^[A-Z]{2}$/.test(query.state)) states.add(query.state);
    }
    return [...states].sort().join(",");
  }, [queries]);

  useEffect(() => {
    if (!statesKey) return;
    let cancel = false;
    for (const state of statesKey.split(",")) {
      loadJson<PacStateFile>(`pac/${state}.json`)
        .then((file) => {
          if (cancel) return;
          setFiles((prev) => (prev[state] ? prev : { ...prev, [state]: file }));
        })
        .catch(() => {
          if (!cancel) setFailed(true);
        });
    }
    return () => {
      cancel = true;
    };
  }, [statesKey]);

  const index = useMemo(() => (crosswalk ? buildIndex(crosswalk) : null), [crosswalk]);
  const models = useMemo(() => {
    if (!index) return null;
    return decideAll(queries, index, files);
  }, [index, queries, files]);

  const panelAt = (slot: number) => {
    if (failed && !models) return <PanelBody model={{ kind: "unavailable" }} />;
    const model = models?.[slot];
    if (!model) return <PanelBody model={{ kind: "pending" }} />;
    if (failed && model.kind === "pending") return <PanelBody model={{ kind: "unavailable" }} />;
    return <PanelBody model={model} />;
  };

  return <>{render(panelAt)}</>;
}
