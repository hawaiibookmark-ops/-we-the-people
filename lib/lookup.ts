import { BASE_PATH, dataUrl } from "./config";
import type {
  FecCandidate,
  HiNominee,
  IncumbentHouse,
  LookupQuery,
  ZipRec,
} from "./types";

type Bundle = {
  zips: Record<string, ZipRec>;
  hawaii: {
    election: { general_date: string; primary_date: string; primary_certified_source: string };
    nominees: Record<string, HiNominee[]>;
    nonpartisan_primary: Record<string, HiNominee[]>;
    islands: Record<
      string,
      { state: string; cds: string[]; split: boolean; note?: string; counties?: string[] }
    >;
    state_filings: {
      wired: boolean;
      csc_public: string;
      csc_searchable: string;
      donors: { status: string; reason: string };
    };
  };
  federal: Record<
    string,
    {
      name: string;
      house: Record<string, FecCandidate[]>;
      senate: FecCandidate[];
      senate_regular_2026: boolean;
      state_filings_wired: boolean;
      state_filings_note: string | null;
    }
  >;
  incumbents: {
    house: Record<string, IncumbentHouse>;
    senate: Record<string, { name: string; votes_url: string; member_url: string; senate_class?: string; party?: string }[]>;
  };
  donors: {
    fec_api_key_present: boolean;
    policy: string;
    by_candidate: Record<
      string,
      { status: string; reason?: string | null; items: { contributor_name: string; amount: number; date?: string; fec_url?: string }[] }
    >;
    retrieved_at: string;
    source: string;
  };
  meta: {
    generated_at: string;
    sources: { url: string; retrieved_at: string; note?: string }[];
    fec_api_key_present: boolean;
    donor_policy: string;
  };
};

let cache: Bundle | null = null;

async function loadJson<T>(file: string): Promise<T> {
  const res = await fetch(dataUrl(file));
  if (!res.ok) throw new Error(`Could not load ${file} (${res.status})`);
  return res.json() as Promise<T>;
}

export async function loadBundle(): Promise<Bundle> {
  if (cache) return cache;
  const [zips, hawaii, federal, incumbents, donors, meta] = await Promise.all([
    loadJson<Bundle["zips"]>("zips.json"),
    loadJson<Bundle["hawaii"]>("hawaii.json"),
    loadJson<Bundle["federal"]>("federal.json"),
    loadJson<Bundle["incumbents"]>("incumbents.json"),
    loadJson<Bundle["donors"]>("donors.json"),
    loadJson<Bundle["meta"]>("meta.json"),
  ]);
  cache = { zips, hawaii, federal, incumbents, donors, meta };
  return cache;
}

export function parseQuery(raw: string): LookupQuery {
  const trimmed = raw.trim();
  const zipMatch = trimmed.match(/\b(\d{5})(?:-\d{4})?\b/);
  const islands = ["Oʻahu", "Oahu", "Maui", "Molokaʻi", "Molokai", "Lānaʻi", "Lanai", "Kauaʻi", "Kauai", "Hawaiʻi Island", "Hawaii Island", "Big Island"];
  const islandHit = islands.find((n) => n.toLowerCase() === trimmed.toLowerCase());
  const islandMap: Record<string, string> = {
    oahu: "Oʻahu",
    "oʻahu": "Oʻahu",
    maui: "Maui",
    molokai: "Molokaʻi",
    "molokaʻi": "Molokaʻi",
    lanai: "Lānaʻi",
    "lānaʻi": "Lānaʻi",
    kauai: "Kauaʻi",
    "kauaʻi": "Kauaʻi",
    "hawaii island": "Hawaiʻi Island",
    "hawaiʻi island": "Hawaiʻi Island",
    "big island": "Hawaiʻi Island",
  };
  return {
    raw: trimmed,
    zip: zipMatch?.[1],
    island: islandHit ? islandMap[islandHit.toLowerCase()] : islandMap[trimmed.toLowerCase()],
    address: /[a-z]/i.test(trimmed) && zipMatch ? trimmed : undefined,
  };
}

function fact<T>(value: T, url: string, retrieved_at: string, label: string) {
  return { value, source: { url, retrieved_at, label } };
}

export type Fact<T> = ReturnType<typeof fact<T>>;

export type CandidateCard = {
  name: string;
  party?: string;
  role: string;
  district?: string;
  incumbent?: boolean;
  primaryVotes?: number;
  list: "general_nominee" | "fec_filing" | "certified_primary";
  fecId?: string;
  fecUrl?: string;
  voteLinks?: { label: string; url: string }[];
  donors: {
    status: "ok" | "empty" | "linked";
    reason: string;
    items: { name: string; amount: number; date?: string }[];
    sourceUrl: string;
  };
  sources: { url: string; retrieved_at: string; label: string }[];
};

export type LookupResult = {
  query: LookupQuery;
  place: {
    zip?: string;
    state?: string;
    stateName?: string;
    island?: string;
    county?: string;
    cds: { district: string; name: string; land: number }[];
    sldu?: { district: string; name?: string };
    sldl?: { district: string; name?: string };
  };
  flags: { title: string; detail: string }[];
  races: {
    title: string;
    candidates: CandidateCard[];
    emptyNote?: string;
  }[];
  stateFilingsNote?: string;
  sourcesUsed: { url: string; retrieved_at: string; label: string }[];
};

function officeHasDist(office: string, dist: string) {
  const n = String(Number(dist));
  return new RegExp(`(?:dist(?:rict)?\\s*)${n}(?!\\d)`, "i").test(office);
}

function padDist(d: string) {
  if (d === "00" || d.toLowerCase() === "al") return "00";
  return d.replace(/\D/g, "").padStart(2, "0") || d;
}

function namesMatch(a: string, b: string) {
  const norm = (s: string) =>
    s
      .toUpperCase()
      .replace(/[^A-Z ]/g, " ")
      .split(/\s+/)
      .filter(Boolean)
      .sort()
      .join(" ");
  const na = norm(a);
  const nb = norm(b);
  if (na === nb) return true;
  const as = new Set(na.split(" "));
  const bs = new Set(nb.split(" "));
  const lastA = a.split(",")[0]?.toUpperCase().replace(/[^A-Z]/g, "");
  const lastB = b.split(",")[0]?.toUpperCase().replace(/[^A-Z]/g, "");
  if (lastA && lastA === lastB && lastA.length > 2) return true;
  let overlap = 0;
  for (const x of as) if (bs.has(x) && x.length > 2) overlap += 1;
  return overlap >= 2;
}

export function runLookup(bundle: Bundle, query: LookupQuery): LookupResult {
  const retrieved = bundle.meta.generated_at;
  const flags: LookupResult["flags"] = [];
  const sourcesUsed: LookupResult["sourcesUsed"] = [];
  const censusCd = bundle.meta.sources.find((s) => s.url.includes("tab20_cd119")) || {
    url: "https://www2.census.gov/geo/docs/maps-data/data/rel2020/cd-sld/tab20_cd11920_zcta520_natl.txt",
    retrieved_at: retrieved,
  };

  let zipRec: ZipRec | undefined;
  let islandName = query.island;
  if (query.zip) zipRec = bundle.zips[query.zip];
  if (!zipRec && islandName) {
    const island = bundle.hawaii.islands[islandName];
    if (island) {
      zipRec = {
        s: "HI",
        cd: island.cds.map((d) => [d, 1, `Congressional District ${Number(d)}`]),
        island: islandName,
        co: island.counties?.[0],
      };
      if (island.split) {
        flags.push({
          title: "Island spans more than one U.S. House district",
          detail: island.note || `${islandName} includes HI-01 and HI-02. Enter a ZIP to see the district that covers your address.`,
        });
      }
    }
  }

  if (!zipRec) {
    return {
      query,
      place: { zip: query.zip, cds: [], island: islandName },
      flags: [
        {
          title: "No Census ZCTA match",
          detail: query.zip
            ? `ZIP ${query.zip} is not in the Census 2020 ZCTA ↔ 119th Congressional District relationship file. Some PO Boxes and unique ZIP codes have no ZCTA.`
            : "Enter a 5-digit ZIP, a street address that includes a ZIP, or a Hawaiʻi island name.",
        },
      ],
      races: [],
      sourcesUsed: [{ url: censusCd.url, retrieved_at: censusCd.retrieved_at, label: "Census ZCTA–CD relationship file" }],
    };
  }

  const state = zipRec.s;
  const cds = zipRec.cd.map(([district, land, name]) => ({ district, land, name }));
  if (cds.length > 1) {
    flags.push({
      title: "ZIP spans more than one U.S. House district",
      detail: `Census ZCTA ${query.zip || ""} overlaps ${cds
        .map((c) => `${state}-${c.district}`)
        .join(", ")} (land-area parts shown). A street address may sit in only one district. Both/all overlaps are listed rather than guessing.`,
    });
  }
  if (query.address && query.zip) {
    flags.push({
      title: "Address looked up by ZIP",
      detail: "This static site cannot call the Census Geocoder from the browser (no CORS). The ZIP inside the address was used. Street-level districts can differ from the ZCTA; overlaps are flagged.",
    });
  }
  if (zipRec.disagreement?.length) {
    flags.push({
      title: "State-district sources differ inside this ZIP",
      detail: `ZCTA internal point and the Hawaii State Capitol address in 96813 disagree on: ${zipRec.disagreement.join(", ")}. Both are shown.`,
    });
  }

  sourcesUsed.push({
    url: censusCd.url,
    retrieved_at: censusCd.retrieved_at,
    label: "Census ZCTA to 119th Congressional District",
  });

  const federal = bundle.federal[state];
  const races: LookupResult["races"] = [];
  const hiOe = bundle.meta.sources.find((s) => s.url.includes("2026%20Primary/summary")) || {
    url: "https://elections.hawaii.gov/wp-content/results/2026%20Primary/summary.txt",
    retrieved_at: retrieved,
  };

  function donorFor(fecId?: string, isHiState?: boolean): CandidateCard["donors"] {
    if (isHiState) {
      return {
        status: "linked",
        reason: bundle.hawaii.state_filings.donors.reason,
        items: [],
        sourceUrl: bundle.hawaii.state_filings.csc_public,
      };
    }
    if (!bundle.donors.fec_api_key_present) {
      return {
        status: "empty",
        reason: bundle.donors.policy,
        items: [],
        sourceUrl: "https://www.fec.gov/data/receipts/individual-contributions/",
      };
    }
    if (!fecId) {
      return {
        status: "empty",
        reason: "No FEC candidate ID matched this name. Donor names are not invented.",
        items: [],
        sourceUrl: "https://www.fec.gov/data/receipts/individual-contributions/",
      };
    }
    const row = bundle.donors.by_candidate[fecId];
    if (!row || !row.items?.length) {
      return {
        status: "empty",
        reason: row?.reason || "No Schedule A $200+ individual receipts returned.",
        items: [],
        sourceUrl: bundle.donors.source,
      };
    }
    return {
      status: "ok",
      reason: "FEC Schedule A individual receipts of $200+ (as returned by OpenFEC).",
      items: row.items.map((i) => ({ name: i.contributor_name, amount: i.amount, date: i.date })),
      sourceUrl: row.items[0]?.fec_url || bundle.donors.source,
    };
  }

  function voteLinks(stateCode: string, dist: string, candidateName: string, isIncumbent: boolean) {
    if (!isIncumbent) return [];
    const key = `${stateCode}-${padDist(dist)}`;
    const inc = bundle.incumbents.house[key];
    if (inc && namesMatch(inc.name, candidateName)) {
      return [
        { label: "Congress.gov roll-call votes", url: inc.votes_url },
        { label: "House Clerk member page", url: inc.clerk_url },
      ];
    }
    return [{ label: "Congress.gov members directory", url: "https://www.congress.gov/members" }];
  }

  function senateVoteLinks(stateCode: string, candidateName: string) {
    const members = bundle.incumbents.senate[stateCode] || [];
    const hit = members.find((m) => namesMatch(m.name, candidateName));
    if (hit) return [{ label: "Congress.gov roll-call votes", url: hit.votes_url }];
    return [];
  }

  // US House races for each overlapping CD
  for (const cd of cds) {
    const dist = padDist(cd.district);
    const fecList = federal?.house?.[dist] || federal?.house?.[cd.district] || [];
    const cards: CandidateCard[] = [];

    if (state === "HI") {
      const office =
        dist === "01" ? "U.S. Representative, Dist I" : dist === "02" ? "U.S. Representative, Dist II" : null;
      const nominees = office ? bundle.hawaii.nominees[office] || [] : [];
      for (const n of nominees) {
        const fecHit = fecList.find((f) => n.name && namesMatch(f.name, n.name));
        const isInc = /incumbent/i.test(fecHit?.incumbent_challenge || "");
        cards.push({
          name: n.name || "Name not listed",
          party: n.party,
          role: `U.S. House ${state}-${dist}`,
          district: dist,
          incumbent: isInc,
          primaryVotes: n.primary_votes ?? undefined,
          list: "general_nominee",
          fecId: fecHit?.candidate_id,
          fecUrl: fecHit?.fec_url,
          voteLinks: voteLinks(state, dist, n.name || "", isInc),
          donors: donorFor(fecHit?.candidate_id),
          sources: [
            { url: hiOe.url, retrieved_at: hiOe.retrieved_at, label: "Hawaii Office of Elections 2026 Primary certified summary (party nominee)" },
            ...(fecHit
              ? [{ url: fecHit.fec_url, retrieved_at: retrieved, label: "FEC candidate filing" }]
              : []),
          ],
        });
      }
      const unmatched = fecList.filter(
        (f) => !nominees.some((n) => n.name && namesMatch(f.name, n.name)),
      );
      if (unmatched.length) {
        flags.push({
          title: `FEC filings disagree with Hawaii certified primary nominees (${state}-${dist})`,
          detail: `${unmatched
            .map((f) => f.name)
            .join("; ")} appear on FEC 2026 filings but are not the Office of Elections certified party nominee for November. Both lists are shown.`,
        });
        for (const f of unmatched) {
          cards.push({
            name: f.name,
            party: f.party,
            role: `U.S. House ${state}-${dist}`,
            district: dist,
            incumbent: /incumbent/i.test(f.incumbent_challenge || ""),
            list: "fec_filing",
            fecId: f.candidate_id,
            fecUrl: f.fec_url,
            voteLinks: [],
            donors: donorFor(f.candidate_id),
            sources: [{ url: f.fec_url, retrieved_at: retrieved, label: "FEC 2026 candidate filing (not OE nominee)" }],
          });
        }
      }
    } else {
      if (!fecList.length) {
        races.push({
          title: `U.S. House ${state}-${dist === "00" ? "At Large" : dist}`,
          candidates: [],
          emptyNote: "No FEC 2026 House filings were returned for this district at retrieval time.",
        });
        continue;
      }
      for (const f of fecList) {
        const isInc = /incumbent/i.test(f.incumbent_challenge || "");
        cards.push({
          name: f.name,
          party: f.party,
          role: `U.S. House ${state}-${dist === "00" ? "At Large" : dist}`,
          district: dist,
          incumbent: isInc,
          list: "fec_filing",
          fecId: f.candidate_id,
          fecUrl: f.fec_url,
          voteLinks: voteLinks(state, dist, f.name, isInc),
          donors: donorFor(f.candidate_id),
          sources: [{ url: f.fec_url, retrieved_at: retrieved, label: "FEC 2026 House candidate filing" }],
        });
      }
    }

    races.push({
      title: `U.S. House ${state}-${dist === "00" ? "At Large" : dist}`,
      candidates: cards,
    });
  }

  // US Senate
  const senateFec = federal?.senate || [];
  const senateCards: CandidateCard[] = [];
  if (federal?.senate_regular_2026) {
    for (const f of senateFec) {
      const isInc = /incumbent/i.test(f.incumbent_challenge || "");
      senateCards.push({
        name: f.name,
        party: f.party,
        role: `U.S. Senate ${state}`,
        incumbent: isInc,
        list: "fec_filing",
        fecId: f.candidate_id,
        fecUrl: f.fec_url,
        voteLinks: senateVoteLinks(state, f.name),
        donors: donorFor(f.candidate_id),
        sources: [{ url: f.fec_url, retrieved_at: retrieved, label: "FEC 2026 Senate candidate filing" }],
      });
    }
    races.push({
      title: `U.S. Senate — ${federal.name}`,
      candidates: senateCards,
      emptyNote: senateCards.length ? undefined : "No FEC 2026 Senate filings were returned for this state at retrieval time.",
    });
  } else {
    if (senateFec.length) {
      flags.push({
        title: "FEC lists Senate filers; no regular 2026 Senate class in this state",
        detail: "Senate class listings (senate.gov) do not show a Class II seat up in 2026 here. FEC 2026 Senate filings are shown separately and are not treated as a November ballot.",
      });
      races.push({
        title: `U.S. Senate filings (not a regular 2026 seat) — ${federal?.name || state}`,
        candidates: senateFec.map((f) => ({
          name: f.name,
          party: f.party,
          role: `U.S. Senate ${state}`,
          list: "fec_filing" as const,
          fecId: f.candidate_id,
          fecUrl: f.fec_url,
          voteLinks: [],
          donors: donorFor(f.candidate_id),
          sources: [{ url: f.fec_url, retrieved_at: retrieved, label: "FEC 2026 Senate filing" }],
        })),
      });
    } else {
      races.push({
        title: `U.S. Senate — ${federal?.name || state}`,
        candidates: [],
        emptyNote: "No regular U.S. Senate election in 2026 for this state (Class II seats are up in 2026). Source: U.S. Senate directory classes.",
      });
    }
  }

  if (state === "HI") {
    const sldu = zipRec.sldu?.district;
    const sldl = zipRec.sldl?.district;
    const statewideOffices = ["Governor", "Lieutenant Governor"];
    for (const office of statewideOffices) {
      const noms = bundle.hawaii.nominees[office] || [];
      races.push({
        title: office,
        candidates: noms.map((n) => ({
          name: n.name || "Name not listed",
          party: n.party,
          role: office,
          primaryVotes: n.primary_votes ?? undefined,
          list: "general_nominee" as const,
          voteLinks: [],
          donors: donorFor(undefined, true),
          sources: [{ url: hiOe.url, retrieved_at: hiOe.retrieved_at, label: "Hawaii Office of Elections 2026 Primary certified summary" }],
        })),
      });
    }
    if (sldu) {
      const senateDistricts = new Set<string>([sldu]);
      if (zipRec.point_check?.sldu?.district) senateDistricts.add(zipRec.point_check.sldu.district);
      for (const dist of senateDistricts) {
        const key = Object.keys(bundle.hawaii.nominees).find(
          (k) => k.toLowerCase().includes("state senator") && officeHasDist(k, dist),
        );
        const noms = (key && bundle.hawaii.nominees[key]) || [];
        races.push({
          title: key || `State Senate District ${Number(dist)}`,
          candidates: noms.map((n) => ({
            name: n.name || "Name not listed",
            party: n.party,
            role: `Hawaii State Senate Dist. ${Number(dist)}`,
            district: dist,
            primaryVotes: n.primary_votes ?? undefined,
            list: "general_nominee" as const,
            donors: donorFor(undefined, true),
            sources: [{ url: hiOe.url, retrieved_at: hiOe.retrieved_at, label: "Hawaii Office of Elections 2026 Primary certified summary" }],
          })),
          emptyNote: noms.length ? undefined : "No certified party nominee row found for this Senate district in the 2026 primary summary.",
        });
      }
    }
    if (sldl || zipRec.point_check?.sldl?.district) {
      const houseDistricts = new Set<string>();
      if (sldl) houseDistricts.add(sldl);
      if (zipRec.point_check?.sldl?.district) houseDistricts.add(zipRec.point_check.sldl.district);
      for (const dist of houseDistricts) {
        const key = Object.keys(bundle.hawaii.nominees).find(
          (k) => k.toLowerCase().includes("state representative") && officeHasDist(k, dist),
        );
        const noms = (key && bundle.hawaii.nominees[key]) || [];
        races.push({
          title: key || `State House District ${Number(dist)}`,
          candidates: noms.map((n) => ({
            name: n.name || "Name not listed",
            party: n.party,
            role: `Hawaii State House Dist. ${Number(dist)}`,
            district: dist,
            primaryVotes: n.primary_votes ?? undefined,
            list: "general_nominee" as const,
            donors: donorFor(undefined, true),
            sources: [{ url: hiOe.url, retrieved_at: hiOe.retrieved_at, label: "Hawaii Office of Elections 2026 Primary certified summary" }],
          })),
          emptyNote: noms.length ? undefined : "No certified party nominee row found for this House district in the 2026 primary summary.",
        });
      }
    }
    if (zipRec.point_check && zipRec.disagreement?.includes("state_house") && zipRec.point_check.sldl) {
      flags.push({
        title: "State House district: ZCTA point vs Capitol address",
        detail: `ZCTA internal point: ${zipRec.sldl?.name || zipRec.sldl?.district}. Capitol address (415 S Beretania St): ${zipRec.point_check.sldl.name || zipRec.point_check.sldl.district}.`,
      });
    }
  } else {
    races.push({
      title: "State and local filings",
      candidates: [],
      emptyNote: federal?.state_filings_note || "State filings not wired yet.",
    });
  }

  return {
    query,
    place: {
      zip: query.zip,
      state,
      stateName: federal?.name,
      island: zipRec.island || islandName,
      county: zipRec.co,
      cds,
      sldu: zipRec.sldu,
      sldl: zipRec.sldl,
    },
    flags,
    races,
    stateFilingsNote: state === "HI" ? undefined : federal?.state_filings_note || "State filings not wired yet.",
    sourcesUsed,
  };
}

export function lookupHref(q: string) {
  const params = new URLSearchParams({ q });
  return `${BASE_PATH}/lookup/?${params.toString()}`;
}
