const STOP_WORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
  "has", "have", "in", "is", "it", "of", "on", "or", "that", "the", "this",
  "to", "was", "with", "va", "la", "cua", "cho", "mot", "nhung", "cac",
  "duoc", "trong", "khi", "nay", "do", "voi", "den", "tu",
]);

function foldAccents(value: string): string {
  return value.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLocaleLowerCase();
}

export function splitSentences(text: string): string[] {
  const segmenter = new Intl.Segmenter(undefined, { granularity: "sentence" });
  return Array.from(segmenter.segment(text), (part) => part.segment.trim()).filter(Boolean);
}

export function wordsOf(text: string): string[] {
  return (
    foldAccents(text)
      .match(/[\p{Letter}\p{Number}]+/gu)
      ?.filter((word) => word.length > 2 && !STOP_WORDS.has(word)) ?? []
  );
}

export function overlapScore(claim: string, sentence: string): number {
  const claimWords = new Set(wordsOf(claim));
  const sentenceWords = new Set(wordsOf(sentence));
  if (claimWords.size === 0 || sentenceWords.size === 0) return 0;

  let sharedWords = 0;
  for (const word of claimWords) {
    if (sentenceWords.has(word)) sharedWords += 1;
  }
  return sharedWords / claimWords.size;
}

export function bestSentenceIndex(
  claim: string,
  sentences: string[],
  threshold = 0.2,
): number {
  let bestIndex = -1;
  let bestScore = threshold;

  sentences.forEach((sentence, index) => {
    const score = overlapScore(claim, sentence);
    if (score > bestScore) {
      bestScore = score;
      bestIndex = index;
    }
  });

  return bestIndex;
}

export function claimForCitation(answer: string, citationNumber: number): string {
  const marker = new RegExp(`\\[${citationNumber}\\]`);
  const sentence = splitSentences(answer).find((part) => marker.test(part));
  return sentence?.replace(/\[\d+\]/g, "").replace(/\s+([.,!?;:])/g, "$1").trim() ?? answer;
}
