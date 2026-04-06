"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob

STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "of", "in", "on", "at", "to",
    "for", "with", "by", "from", "into", "about", "as", "or", "and", "but",
    "not", "no", "so", "if", "its", "it", "this", "that", "these", "those",
    "there", "their", "they", "any", "all", "how", "what", "which", "where",
    "when", "who", "i", "my", "your", "our", "me", "we", "us",
}

class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, chunk) where each chunk is one
        paragraph (split on blank lines). Empty paragraphs are dropped.
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                for chunk in text.split("\n\n"):
                    chunk = chunk.strip()
                    if chunk:
                        docs.append((filename, chunk))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        TODO (Phase 1):
        Build a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Example structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Keep this simple: split on whitespace, lowercase tokens,
        ignore punctuation if needed.
        """
        index = {}
        for filename, text in documents:
            words = text.lower().split()
            seen = set()
            for word in words:
                token = word.strip(".,!?;:\"'()")
                if token and token not in seen:
                    index.setdefault(token, []).append(filename)
                    seen.add(token)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        TODO (Phase 1):
        Return a simple relevance score for how well the text matches the query.

        Suggested baseline:
        - Convert query into lowercase words
        - Count how many appear in the text
        - Return the count as the score
        """
        text_lower = text.lower()
        query_tokens = [
            w.strip(".,!?;:\"'()") for w in query.lower().split()
        ]
        content_tokens = [t for t in query_tokens if t and t not in STOPWORDS]
        score = sum(1 for token in content_tokens if token in text_lower)
        return score

    def retrieve(self, query, top_k=3, min_score=2):
        """
        Use the index and scoring function to select top_k relevant chunks.

        min_score: minimum number of query tokens that must appear in a chunk
        for it to be considered useful evidence. Chunks below this threshold
        are discarded before ranking. Returns [] if nothing clears the bar,
        which causes the answer methods to issue a refusal.

        Return a list of (filename, chunk) sorted by score descending.
        """
        # Use the index to find candidate filenames containing query tokens
        query_tokens = [w.strip(".,!?;:\"'()") for w in query.lower().split()]
        content_tokens = [t for t in query_tokens if t and t not in STOPWORDS]
        candidates = set()
        for token in content_tokens:
            if token in self.index:
                candidates.update(self.index[token])

        # Score each candidate chunk; drop anything below min_score
        scored = []
        for filename, chunk in self.documents:
            if filename in candidates:
                score = self.score_document(query, chunk)
                if score >= min_score:
                    scored.append((score, filename, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [(filename, chunk) for _, filename, chunk in scored]
        return results[:top_k]

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
