# US Virgin Islands `/data/vi/` schema

| Path | Role |
| --- | --- |
| `/data/vi.json` | Territory stub. `prefer_for_november=official_august`. `no_us_senate=true`. `primary_certified=2026-08-25`. |
| `/data/vi/candidates.json` | 166 official rows, 9 `contest_key`s, `complete=true`. June listing / August general / FEC Delegate. |
| `/data/vi/candidate-summary.json` | Counts + `source_url` + `retrieved_at`. |
| `/data/vi/fec-donors.json` | Federal FEC Schedule A $200+ (9/4/326). Territorial CF is not here. |
| `/data/vi/votes.json` | Federal-only Clerk EVS, `complete=false`. No Senate rows. |
| `/data/vi/SOURCE_META.json` | Coordination metadata. Primary certification is Aug 25, not June 17. |
| `/data/vi/NOTES.md` | Human notes. |
| `/data/vi/DISCOVERY.md` | Official source URLs. |

Candidate row fields: `state`, `contest_key` (`VI\|OFFICE\|DIST\|`), `office`, `district`, `party`, `candidate_name`, `list_kind`, `election`, `election_date`, `complete`, `source_url`, `retrieved_at`. Streets / email / phone omitted.

Vote row fields match other state extracts: Clerk `vote_cast` is the exact official text. Votes are never invented.
