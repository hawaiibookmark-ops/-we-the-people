import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  buildIndex,
  countCrosswalkPanels,
  decideAll,
  noneReportedText,
  notFoundText,
  type PacQuery,
  type PacStateFile,
} from "../lib/pacMatch.ts";

const root = new URL("../public/data/pac/", import.meta.url);

function load(name: string): PacStateFile & { rows?: unknown[] } {
  return JSON.parse(readFileSync(new URL(name, root), "utf8"));
}

const crosswalk = load("crosswalk.json") as { rows: Parameters<typeof buildIndex>[0] };
const index = buildIndex(crosswalk.rows);
const counts = countCrosswalkPanels(crosswalk.rows);
assert.deepEqual(counts, { matched: 4327, ambiguous: 10, notInFec: 72 });

function q(partial: PacQuery): PacQuery {
  return partial;
}

const files: Record<string, PacStateFile> = {
  HI: load("HI.json"),
  AZ: load("AZ.json"),
  FL: load("FL.json"),
  MO: load("MO.json"),
  TX: load("TX.json"),
  CO: load("CO.json"),
};

function one(query: PacQuery) {
  const [model] = decideAll([query], index, files);
  return model;
}

const tokuda = one(
  q({
    scope: "federal",
    state: "HI",
    office: "U.S. House",
    district: "02",
    name: "TOKUDA, Jill N.",
    siteCandidateId: "H2HI02581",
  }),
);
assert.equal(tokuda.kind, "matched");
if (tokuda.kind === "matched") {
  const pac = tokuda.sections[0];
  assert.equal(pac.count, 95);
  assert.equal(pac.total, 185450);
  assert.equal(tokuda.unconfirmed, false);
  assert.equal(tokuda.combinesNote, null);
}

const awa = one(
  q({
    scope: "federal",
    state: "HI",
    office: "U.S. House",
    district: "02",
    name: "AWA, Brenton",
    siteCandidateId: "H6HI02426",
  }),
);
assert.equal(awa.kind, "matched");
if (awa.kind === "matched") {
  for (const section of awa.sections) {
    assert.equal(section.count, 0);
    assert.equal(noneReportedText(section.dataAsOf), "None reported as of 2026-09-27");
  }
}

const ed = one(
  q({
    scope: "federal",
    state: "HI",
    office: "U.S. House",
    district: "01",
    name: "CASE, Ed",
  }),
);
assert.equal(ed.kind, "matched");
if (ed.kind === "matched") {
  assert.equal(ed.sections[0].count, 280);
  assert.equal(ed.sections[0].total, 486640);
}

const galan = one(
  q({
    scope: "federal",
    state: "AZ",
    office: "U.S. House",
    district: "01",
    name: "GALAN-WOODS, MARLENE",
    siteCandidateId: "H6AZ01280",
  }),
);
assert.equal(galan.kind, "matched");
if (galan.kind === "matched") {
  assert.deepEqual(
    galan.fecLinks.map((link) => link.id),
    ["H4AZ01228"],
  );
  assert.equal(galan.sections[0].count, 11);
  assert.equal(galan.sections[0].total, 19046);
  assert.ok(galan.sections[0].total > 0);
  assert.notEqual(noneReportedText("2026-09-27"), `PAC ${galan.sections[0].count}`);
}

for (const [name, state, district, stale, corrected] of [
  ["VEREEN, RODERICK DARRELL", "FL", "24", "H6FL24103", "H0FL17092"],
  ["SMITH, SEAN", "MO", "05", "H6MO05296", "H4MO05366"],
  ["HOCKETT, CHELSEY ALEXANDRA", "TX", "05", "H6TX05197", "H6TX05189"],
  ["RAASCH, WAYNE", "TX", "27", "H6TX27068", "H2TX05170"],
] as const) {
  const model = one(
    q({
      scope: "federal",
      state,
      office: "U.S. House",
      district,
      name,
      siteCandidateId: stale,
    }),
  );
  assert.equal(model.kind, "matched", name);
  if (model.kind === "matched") {
    assert.equal(model.fecLinks[0]?.id, corrected, name);
    assert.ok(!model.fecLinks.some((link) => link.id === stale), name);
    assert.equal(model.unconfirmed, name === "RAASCH, WAYNE");
  }
}

const greeneQueries: PacQuery[] = [
  q({
    scope: "federal",
    state: "AZ",
    office: "U.S. House",
    district: "08",
    name: "GREENE PLACENTIA, BERNADETTE",
    siteCandidateId: "H4AZ08082",
  }),
  q({
    scope: "federal",
    state: "AZ",
    office: "U.S. House",
    district: "00",
    name: "",
    siteCandidateId: "H6AZ08210",
  }),
];
const greene = decideAll(greeneQueries, index, files);
assert.equal(greene[0].kind, "matched");
assert.equal(greene[1].kind, "hidden");
if (greene[0].kind === "matched") {
  assert.deepEqual(
    greene[0].fecLinks.map((link) => link.id),
    ["H4AZ08082", "H6AZ08210"],
  );
  assert.equal(greene[0].sections[0].count, 1);
  assert.equal(greene[0].sections[0].total, 2500);
  assert.equal(greene[0].combinesNote, "Combines FEC IDs H4AZ08082, H6AZ08210 (duplicate registrations of the same candidate).");
  assert.equal(greene[0].unconfirmed, false);
  assert.equal(greene.filter((panel) => panel.kind === "matched").length, 1);
}

const fillmore = one(
  q({
    scope: "federal",
    state: "AZ",
    office: "U.S. House",
    district: "04",
    name: "Fillmore, John",
  }),
);
assert.equal(fillmore.kind, "not-found");
if (fillmore.kind === "not-found") {
  assert.equal(notFoundText(fillmore.dataAsOf), "Not found in FEC candidate filings as of 2026-09-27.");
  assert.equal(JSON.stringify(fillmore).includes("H8AZ01047"), false);
}

const hanksQueries: PacQuery[] = [
  q({
    scope: "federal",
    state: "CO",
    office: "U.S. House",
    district: "03",
    name: "HANKS, RON",
    siteCandidateId: "H6CO03279",
  }),
  q({
    scope: "federal",
    state: "CO",
    office: "U.S. House",
    district: "03",
    name: "Ron Hanks",
  }),
];
const hanks = decideAll(hanksQueries, index, files);
assert.equal(hanks[0].kind, "matched");
assert.equal(hanks[1].kind, "hidden");
if (hanks[0].kind === "matched") {
  assert.deepEqual(
    hanks[0].fecLinks.map((link) => link.id),
    ["H6CO03279", "H4CO03407"],
  );
  assert.match(hanks[0].combinesNote || "", /Combines FEC IDs H6CO03279, H4CO03407/);
  assert.equal(hanks.filter((panel) => panel.kind === "matched").length, 1);
}

const clemmons = one(
  q({
    scope: "federal",
    state: "CA",
    office: "U.S. House",
    district: "41",
    name: "Mitch Clemmons",
  }),
);
assert.equal(clemmons.kind, "pending");
const clemmonsReady = decideAll(
  [
    q({
      scope: "federal",
      state: "CA",
      office: "U.S. House",
      district: "41",
      name: "Mitch Clemmons",
    }),
  ],
  index,
  { CA: { data_as_of: "2026-09-27", by_candidate: {} } },
);
assert.equal(clemmonsReady[0].kind, "ambiguous");
if (clemmonsReady[0].kind === "ambiguous") {
  assert.deepEqual(
    clemmonsReady[0].blocks.map((block) => block.id),
    ["H2CA38260", "H6CA41380"],
  );
}

const codelia = one(
  q({
    scope: "federal",
    state: "HI",
    office: "U.S. House",
    district: "02",
    name: "CODELIA, Edward A.",
  }),
);
assert.equal(codelia.kind, "not-found");

console.log("pac match tests ok", counts);
