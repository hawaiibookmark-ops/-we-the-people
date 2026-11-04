export type ResultCandidate = {
  name: string;
  party?: string | null;
  votes: number;
  pct?: number | null;
  rank?: number;
  incumbent?: boolean | null;
  incumbent_source?: string;
  write_in?: boolean;
  official_page_marker?: string | null;
};

export type ResultContest = {
  id: string;
  office: string;
  district?: string | null;
  title: string;
  jurisdiction?: string | null;
  vote_for?: number;
  status: string;
  total_votes: number;
  candidates: ResultCandidate[];
  reporting?: { unit: string; reporting: number | null; total: number | null } | null;
  results_as_of?: string | null;
  source_url: string;
  retrieved_at: string;
  leading?: string | null;
  margin_votes?: number;
  margin_pct?: number;
  notes?: string;
  blank_votes?: number;
  over_votes?: number;
  pct_basis?: string;
};

export type ResultsState = {
  state: string;
  name: string;
  status: string;
  results_status: "unofficial_results" | "pending";
  source_url?: string | null;
  retrieved_at: string;
  results_as_of?: string | null;
  contests: ResultContest[];
  notes?: string | null;
  pending_reason?: string;
  links?: Record<string, string>;
  official_pdfs?: Record<string, string>;
};

export type ResultsIndexEntry = {
  state: string;
  name: string;
  status: string;
  results_status: "unofficial_results" | "pending";
  contests: number;
  by_office: Record<string, number>;
  source_url?: string | null;
  retrieved_at: string;
  results_as_of?: string | null;
  file: string;
  notes?: string | null;
};

export type ResultsIndex = {
  generated_at: string;
  status_label: string;
  rules: string[];
  states: ResultsIndexEntry[];
  counts: { states_with_results: number; states_pending: number };
};
