# Query Transformations — HyDE's Siblings (Phase 5 preview)

**TL;DR:** HyDE is one member of a family called **query transformations** —
techniques that rewrite the query *before* search. All of them live at the
same seam in `retriever.py`, and all of them get validated by the same eval.

## The family

All three live at the same "rewrite the query before search" stage:

```
                       ┌─ Multi-Query:    N rephrasings → N searches → RRF fuse
question → transform ──┼─ Decomposition:  sub-questions → search each → combine
                       └─ HyDE:           fake answer → one search
                                ↓
                    same dense/BM25/rerank machinery after this point
```

**Multi-Query.** Rephrase the question N ways, search with all of them, fuse
the result lists with RRF — the *same* fusion already built in Phase 3
([`fusion.py`](../../docsmind/retrieval/fusion.py)). Attacks phrasing luck:
any single phrasing might miss; five phrasings rarely all miss.

**Decomposition.** Split a multi-hop question into sub-questions, retrieve per
sub-question. "How does a neutron star differ from a black hole?" becomes one
search about neutron stars and one about black holes — because no single chunk
answers the comparison, but two chunks together do.

**HyDE.** Transform the question into answer-shaped text
(see [problem-and-fix.md](problem-and-fix.md)).

## Same seam, different failure modes

| Technique | Extra LLM calls | Extra searches | Fails when |
|---|---|---|---|
| Multi-Query | 1 (generates N rephrasings) | N | Rephrasings are all synonyms of the same miss |
| Decomposition | 1 (splits the question) | one per sub-question | The split loses the connective logic of the question |
| HyDE | 1 (writes fake answer) | 1 | The fake answer is off-topic — retrieval steered wrong |

The shared cost: every one of them puts an LLM call in front of retrieval.
The shared payoff: they help most on exactly the queries plain dense search
fumbles — vague, multi-part, or vocabulary-poor questions.

## Why these belong to Phase 5, not Phase 3

Phase 3 (hybrid) improved *how* we search with a fixed query. Query
transformations change *what* we search with — and choosing when to apply
which rewrite is a decision. A static pipeline can't decide; an agent can.
That's the whole reason `docsmind/agent/` exists on the roadmap: a loop that
can look at a question and pick "plain search," "HyDE," or "decompose first."

When Phase 5 lands, each of these gets the full treatment: insertion point,
eval numbers, and the honest "did it beat hybrid?" verdict — same discipline
as [09-hybrid-retrieval/eval-results.md](../09-hybrid-retrieval/eval-results.md).

→ Next: **[12-tool-calling/README.md](../12-tool-calling/README.md)**
