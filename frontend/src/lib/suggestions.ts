import type { Page } from "../api/types";
import { strings } from "../strings";
import { cleanDisplayTitle } from "./text";

function titleAtWordBoundary(title: string, maxLength = 48): string {
  const cleanedTitle = cleanDisplayTitle(title).trim();
  if (cleanedTitle.length <= maxLength) return cleanedTitle;

  const shortened = cleanedTitle.slice(0, maxLength);
  const lastSpace = shortened.lastIndexOf(" ");
  return `${shortened.slice(0, lastSpace > 0 ? lastSpace : maxLength).trim()}…`;
}

function hasVietnameseDiacritics(text: string): boolean {
  return /[ăâđêôơưàáạảãằắặẳẵầấậẩẫèéẹẻẽềếệểễìíịỉĩòóọỏõồốộổỗờớợởỡùúụủũừứựửữỳýỵỷỹ]/i.test(text);
}

export function suggestedQuestionsForPages(pages: Page[]): string[] {
  if (pages.length === 0) return [...strings.genericQuestions];

  const latestReadyPages = pages
    .filter((page) => page.status === "ready")
    .toSorted((left, right) => right.fetched_at.localeCompare(left.fetched_at))
    .slice(0, 3);

  return latestReadyPages.map((page) => {
    const title = titleAtWordBoundary(page.title);
    return strings.questionForTitle(title, hasVietnameseDiacritics(page.title));
  });
}
