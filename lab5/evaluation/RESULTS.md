# Movie Memory Agent Evaluation

## Setup

- Corpus: `movies-90s-2000s.catalog.json` (20 films, 4 sequel edges)
- Memory backend: xray-memory snapshot map `movies-90s-2000s`
- Agent: `movie-memory-agent`
- Model configuration: `default-model-config` (`gpt-4.1-mini`)
- Allowed MCP tools: `search_graph`, `get_graph_node`, `get_graph_stats`
- Retrieval rule: the agent must search only the `movies-90s-2000s` map.

## Test procedure

For each query in `movie-retrieval-cases.json`, start a fresh agent turn and
record the returned film, whether the answer includes every required fact, and
the retrieved rank when it is visible in xray. Use a check mark only after
observing the agent output; do not infer a pass from the expected answer.

| Case | Query | Expected document | Top-1 | Top-3 | Answer correct | Evidence / observed answer |
| --- | --- | --- | --- | --- | --- | --- |
| q01 | Who directed the first Matrix film? | `matrix-1999` | Pass | Pass | Pass | `The Matrix` (1999); Lana and Lilly Wachowski. |
| q02 | Which film features a protagonist who cannot form new memories and uses tattoos? | `memento-2000` | Pass | Pass | Pass | `Memento` (2000); Leonard Shelby, photographs, and tattoos. |
| q03 | Name the second Matrix trilogy film and its release year. | `matrix-reloaded-2003` | Fail | Fail | Fail | Agent reported that the second Matrix film was absent. This is a false negative: `The Matrix Reloaded` is in the corpus. |
| q04 | Which film tells the story of banker Andy Dufresne in prison? | `shawshank-redemption-1994` | Pass | Pass | Pass | `The Shawshank Redemption` (1994), directed by Frank Darabont. |
| q05 | In which film is the protagonist's whole life a reality television show? | `truman-show-1998` | Pass | Pass | Pass | `The Truman Show` (1998), directed by Peter Weir. |
| q06 | Find the film about the gladiator Maximus and name its director. | `gladiator-2000` | Pass | Pass | Pass | `Gladiator` (2000), directed by Ridley Scott. |
| q07 | Which Lord of the Rings installment was released in 2002? | `lotr-two-towers-2002` | Pass | Pass | Pass | `The Lord of the Rings: The Two Towers`. |
| q08 | In which film does a waste-collecting robot meet EVE? | `walle-2008` | Fail | Fail | Fail | Agent reported that the film was absent. This is a false negative: `WALL-E` is in the corpus. |
| q09 | Who directed The Dark Knight, and who is its main antagonist? | `dark-knight-2008` | Pass | Pass | Pass | Christopher Nolan; the Joker. |
| q10 | Find the film in which a psychologist helps a boy who sees dead people. | `sixth-sense-1999` | Pass | Pass | Pass | `The Sixth Sense` (1999), directed by M. Night Shyamalan. |

## Negative control

Ask: **"Who directed Titanic?"**

Expected behaviour: the agent states that the fact is absent from the movie
catalog and does not answer from outside knowledge.

Observed result: **Pass.** The agent answered: "The requested fact about who
directed Titanic is not in the movie catalog." It invoked `search_graph` once
and did not use outside knowledge.

## Observed result

- All 16 MCP tool calls completed successfully.
- **Top-1 recall: 8/10 = 80%.** The expected document was used for eight
  questions; the agent returned a false absence for q03 and q08.
- **Top-3 recall: 8/10 = 80%.** The two missed entries were not surfaced in
  the agent's observed retrieval path.
- **Answer accuracy: 8/10 = 80%.** Every successful answer included the
  required facts; no answer used outside knowledge.

The two false negatives suggest an improvement: add title aliases and a
retrieval retry that expands an initially unsuccessful semantic query with
salient terms (for example, `Matrix Reloaded` or `WALL-E`). This was not
applied during the measured run so that the reported baseline stays
reproducible.

## Metric definitions

- **Top-1 recall** = cases where the expected document is ranked first / 10.
- **Top-3 recall** = cases where the expected document appears in the first
  three results / 10.
- **Answer accuracy** = cases with all required answer facts / 10.

Attach screenshots or chat exports for at least three successful cases and the
negative control.
