export type SourceRef = {
  url: string;
  retrieved_at: string;
  note?: string;
};

export type ZipCd = [district: string, land: number, name: string];

export type ZipRec = {
  s: string;
  cd: ZipCd[];
  co?: string;
  cog?: string;
  island?: string | null;
  sldu?: { geoid?: string; name?: string; district: string };
  sldl?: { geoid?: string; name?: string; district: string };
  point_check?: {
    address?: string;
    sldu?: { district: string; name?: string };
    sldl?: { district: string; name?: string };
  };
  disagreement?: string[];
};

export type FecCandidate = {
  name: string;
  party?: string;
  office: string;
  district: string;
  candidate_id: string;
  incumbent_challenge?: string;
  candidate_status?: string;
  fec_url: string;
};

export type HiNominee = {
  office: string;
  kind: string;
  district: string | null;
  party: string;
  party_code: string;
  name: string | null;
  primary_votes: number | null;
  field: string;
};

export type IncumbentHouse = {
  name: string;
  bioguide: string;
  party: string;
  state: string;
  district: string;
  votes_url: string;
  member_url: string;
  clerk_url: string;
};

export type LookupQuery = {
  raw: string;
  zip?: string;
  island?: string;
  address?: string;
};
