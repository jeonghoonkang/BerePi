import numpy as np

class SimpleRAGFlow:
    """A minimal in-memory RAG pipeline used when ragflow library is unavailable."""

    def __init__(self, client, embed_model="text-embedding-3-small", llm_model="gpt-4o-mini"):
        self.client = client
        self.embed_model = embed_model
        self.llm_model = llm_model
        self.docs = []
        self.embs = []

    def add_document(self, text: str):
        """Store text and its embedding."""
        emb_resp = self.client.embeddings.create(model=self.embed_model, input=[text])
        emb = np.array(emb_resp.data[0].embedding)
        self.docs.append(text)
        self.embs.append(emb)

    def query(self, question: str) -> str:
        """Retrieve relevant text and ask LLM for an answer."""
        if not self.docs:
            prompt = question
        else:
            q_emb_resp = self.client.embeddings.create(model=self.embed_model, input=[question])
            q_emb = np.array(q_emb_resp.data[0].embedding)
            sims = [float(np.dot(q_emb, e) / (np.linalg.norm(q_emb) * np.linalg.norm(e))) for e in self.embs]
            best_idx = int(np.argmax(sims))
            context = self.docs[best_idx]
            prompt = f"다음 명함 정보:\n{context}\n\n질문: {question}"
        resp = self.client.chat.completions.create(
            model=self.llm_model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content
