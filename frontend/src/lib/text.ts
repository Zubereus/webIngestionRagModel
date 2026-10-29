export function cleanDisplayTitle(title: string): string {
  return title.replace(/\s*¶+\s*$/u, "").trim();
}
