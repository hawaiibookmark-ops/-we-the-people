export const BASE_PATH = "/-we-the-people";

export function dataUrl(file: string): string {
  return `${BASE_PATH}/data/${file}`;
}

export function partyName(code: string | undefined): string {
  const map: Record<string, string> = {
    D: "Democratic Party",
    R: "Republican Party",
    G: "Green Party",
    L: "Libertarian Party",
    N: "Nonpartisan",
    NON: "Nonpartisan",
  };
  return map[code || ""] || code || "Party not listed on source";
}
