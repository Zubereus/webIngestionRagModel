import assert from "node:assert/strict";
import test from "node:test";
import {
  bestSentenceIndex,
  claimForCitation,
  overlapScore,
  splitSentences,
  wordsOf,
} from "./trace.ts";

test("splits English passage into sentences", () => {
  assert.deepEqual(
    splitSentences("RAG retrieves sources. It answers with evidence."),
    ["RAG retrieves sources.", "It answers with evidence."],
  );
});

test("extracts Vietnamese words without accent differences", () => {
  assert.deepEqual(wordsOf("Tài liệu và tìm kiếm"), ["tai", "lieu", "tim", "kiem"]);
});

test("scores shared words between English sentences", () => {
  assert.equal(
    overlapScore("RAG retrieves relevant sources", "RAG retrieves relevant sources"),
    1,
  );
});

test("finds the closest Vietnamese sentence", () => {
  const passage = "Hệ thống lưu các trang web. Mô hình truy xuất tài liệu và tạo câu trả lời.";
  assert.equal(
    bestSentenceIndex("truy xuất tài liệu tạo câu trả lời", splitSentences(passage)),
    1,
  );
});

test("does not highlight a sentence below the match threshold", () => {
  assert.equal(
    bestSentenceIndex("Retrieval ranks documents", splitSentences("The garden needs water.")),
    -1,
  );
});

test("extracts the answer sentence associated with a citation", () => {
  assert.equal(
    claimForCitation("RAG retrieves useful documents [2]. Another claim [1].", 1),
    "Another claim.",
  );
});
