# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**

DocuBot is basically a tool that answers developer questions by looking through a project’s documentation files. In this assignment, we compared three different approaches: just using an LLM on its own, a simple keyword-based retrieval system, and a combined retrieval plus generation setup. The goal was to see how each one behaves in practice and where they can either be helpful or kinda misleading depending on the situation. Overall, it shows how important it is for AI to actually use real context instead of just sounding right all the time, especially when working with project-specific info that the model wouldn’t otherwise know.

**What inputs does DocuBot take?**

DocuBot takes in a few main inputs. First, it gets a natural language question from the user, like something you’d normally just type out. It also uses the markdown and text files inside the docs/ folder as its main source of information. On top of that, it can use a Gemini API key, which is needed if you’re running the modes that involve the LLM, but not required for the basic retrieval mode.

**What outputs does DocuBot produce?**

DocuBot gives different types of outputs depending on which mode you’re using. In Mode 2, it just returns the raw text from the most relevant paragraph chunks, along with which file they came from, so it’s more like showing the evidence directly. In Modes 1 and 3, it produces a more natural language answer that’s easier to read, but if there isn’t enough solid information in the docs, it can also just say that it doesn’t know instead of guessing, which makes it more relaiable.

---

## 2. Retrieval Design

**How does your retrieval system work?**

- **Indexing:** For indexing, the documents are first split into smaller paragraph-sized chunks by breaking on blank lines, and each chunk is stored along with its filename. Then an inverted index is built that maps important words to the files they appear in, which makes searching faster.
- **Scoring:**For scoring, the system takes the user’s question, splits it into words, removes common filler words like “the” or “is,” and then checks how many of the remaining words appear in each chunk. The more overlap there is, the higher the score, which means the chunk is more relevant.
- **Selection:** For selection, the system first narrows down to only the files that share at least one important word with the query. Then it scores each chunk, filters out anything below a certain threshold, and returns the top few matches based on score. This helps keep the results more focused and not just full of random or weak matches.

**What tradeoffs did you make?**

There were a few tradeoffs in how I designed the retrieval system. For chunking, I went with splitting by paragraphs because it’s simple and keeps related ideas together, but the downside is that some paragraphs can still be too long or mix multiple topics. For scoring, I used basic token overlap, which is easy to implement and consistent, but it treats every word the same. That means it can’t tell the difference between more important words and really common ones, which sometimes led to slightly off results during testing. I also added a minimum score threshold to filter out weak matches, which helps avoid returning random or irrelevant chunks on vague questions. The tradeoff is that it can be a bit too strict, and might skip over a useful result if the query only has one strong keyword, which made it feel a little inflexbile in some cases.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**

- **Naive LLM mode:** In naive mode, it sends just the user’s question to Gemini, without actually including the docs in the prompt, so the model is basically answering from what it already knows instead of the project itself.
- **Retrieval only mode:** In retrieval-only mode, the LLM isn’t used at all. The system just returns the raw text chunks it found, so everything comes directly from the docs with no extra processing.
- **RAG mode:** In RAG mode, the LLM is only called after the retrieval step finds useful chunks. If nothing relevant is found, the system doesn’t even try to generate an answer and instead just returns a refusal. This makes sure it doesn’t guess when there isn’t enough evidence, which makes the behavior more consisent overall.

**What instructions do you give the LLM to keep it grounded?**

In RAG mode, the prompt is set up to keep the model grounded in the actual docs instead of letting it guess. It tells the LLM to only use the information from the provided snippets when answering and to not make up any functions, endpoints, or config details that aren’t explicitly there. It also includes a strict rule where if the snippets don’t have enough info, the model has to respond with “I do not know based on the docs I have.” instead of trying to fill in gaps. On top of that, it asks the model to mention which files it used, so you can clearly see where the answer is coming from.

---

## 4. Experiments and Comparisons

Queries tested identically across all three modes:

| Query | Naive LLM | Retrieval only | RAG | Notes |
|-------|-----------|----------------|-----|-------|
| How does a client refresh an access token? | Harmful — long generic OAuth tutorial, no relation to this app's actual `/api/refresh` endpoint | Harmful — near-miss: returned "access token" chunks, not the refresh endpoint chunk | Helpful — correctly refused because retrieved evidence didn't support an answer | Retrieval missed `POST /api/refresh` because "token" outscored "refresh" |
| Is there any mention of payment processing in these docs? | Harmful — asked the user to provide the docs it already had (corpus not passed to prompt) | Helpful — guardrail fired, clean refusal | Helpful — guardrail fired before LLM was called, clean refusal | Mode 1 has a code bug: `all_text` is built but ignored |

**What patterns did you notice?**

- **When does naive LLM look impressive but untrustworthy?** On questions that have
  well-known general answers. "How does token refresh work?" has a standard OAuth
  answer the model knows confidently — but that answer may not match how this specific
  app implements it. The output reads like authoritative documentation while being
  entirely disconnected from the actual codebase.

- **When is retrieval only clearly better?** When the question is out-of-scope.
  Mode 2 correctly refused the payment processing question because no chunk scored
  above the threshold. Mode 1 invented a non-answer.

- **When is RAG clearly better than both?** When retrieval surfaces the right chunk.
  RAG condenses raw fragments into a readable answer and cites its sources, whereas
  Mode 2 dumps the raw text and Mode 1 ignores the docs entirely.

---

## 5. Failure Cases and Guardrails

**Failure case 1 — Retrieval near-miss causes silent refusal**

- Question: "How does a client refresh an access token?"
- What happened: The chunk for `POST /api/refresh` exists in `API_REFERENCE.md` but
  scored lower than chunks that densely mention "access token" in other contexts.
  Mode 2 returned the wrong chunks; Mode 3 correctly refused given those chunks.
- What should have happened: The refresh endpoint chunk should have been retrieved,
  and Mode 3 should have been able to give a direct answer.

**Failure case 2 — Naive mode ignores its own corpus**

- Question: "Is there any mention of payment processing in these docs?"
- What happened: Mode 1 replied asking the user to provide the documents, even though
  the full corpus was loaded and available.
- What should have happened: The corpus text should be included in the prompt so the
  model can actually scan it. This is a bug in `naive_answer_over_full_docs`: the
  `all_text` parameter is received but never used.

**When should DocuBot say "I do not know based on the docs I have"?**

1. When no chunk in the corpus scores above `min_score` for the query — the topic is
   simply not covered in the documentation.
2. When chunks are retrieved but the LLM determines they don't actually answer the
   question — the right file was found but the specific detail is missing.

**What guardrails did you implement?**

- **Stopword filtering in scoring:** Common words ("is", "the", "any", "in") are
  excluded before scoring so they don't inflate relevance for unrelated chunks.
- **`min_score=2` threshold in `retrieve`:** Chunks must match at least 2 content
  tokens from the query. Single-word overlaps are not treated as evidence.
- **Hard refusal when snippets list is empty:** Both `answer_retrieval_only` and
  `answer_rag` return a fixed refusal string when `retrieve` returns nothing.
- **LLM-level refusal in the RAG prompt:** The prompt explicitly instructs Gemini to
  say "I do not know based on the docs I have." if the provided snippets are
  insufficient — a second layer of guardrail after retrieval.

---

## 6. Limitations and Future Improvements

**Current limitations**

1. Token overlap scoring is order-insensitive and weight-insensitive — "refresh token"
   and "token refresh" score identically, and a rare word like "refresh" counts the
   same as a common word like "token".
2. The naive mode prompt ignores the corpus it was given, making it a general-purpose
   LLM call rather than a doc-grounded one.
3. Paragraph chunking can split mid-thought or group unrelated sentences if the author
   didn't use blank lines consistently.

**Future improvements**

1. Replace token-count scoring with TF-IDF, which down-weights common terms and
   up-weights rare, distinctive ones. This would fix the refresh/token near-miss.
2. Fix the naive mode prompt to actually include `all_text` so Mode 1 is a meaningful
   grounded baseline rather than a pure model recall test.
3. Return the relevance score alongside retrieved chunks in Mode 2 output so the user
   can see how confident the retrieval was.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**

Mode 1 produces confident, well-formatted answers that have no relationship to the
actual codebase. A developer who trusts that output could implement the wrong auth
flow, call endpoints that don't exist, or miss security-critical configuration steps
that are specific to this project. The output looks like documentation, which makes
the hallucination harder to detect.

**What instructions would you give real developers who want to use DocuBot safely?**

- Always check which source files DocuBot cites. If no file is mentioned, the answer
  came from the model's training data, not from your docs.
- Treat Mode 2 output as evidence, not as an answer. Read the retrieved chunks
  yourself before acting on them.
- Use Mode 3 for day-to-day questions, but verify critical details (security config,
  endpoint parameters) against the source files directly.
- Do not use Mode 1 for project-specific questions. It is a baseline for comparison, not a reliable assistant.

---
