# ADR-003: Multilingual Text Embedding Model for Abox

## Status and context

Accepted for the lab; Qwen deployment and quality still need verification in Codespace.
Clarification on 2026-09-22: documents and queries will be in Ukrainian, Russian,
and English. This supersedes the initial choice of Nomic v1.5 in this ADR.

We need a local HTTP endpoint that converts text into a vector. Qdrant stores and
compares vectors; installing Qdrant does not start an embedding model. The client
must call the model both when indexing a document and when searching.
Abox currently provides infrastructure, but no RAG application.

Selection criteria: multilingual support, CPU inference, available GGUF weights,
a verifiable HTTP contract, and support for exploring Matryoshka embeddings.

The existing course cluster already serves `nomic-embed-text-v1.5`. On
2026-09-22, a request through llama.cpp returned HTTP 200, 768 finite values, and
an L2 norm of approximately 1.0. This is a useful deployment baseline, but it does
not change the multilingual model decision: the tested Nomic model card is tagged
English, while the target corpus is multilingual.

## Decision

Use **Qwen/Qwen3-Embedding-0.6B**, the official **Q8_0 GGUF**, and **llama.cpp**.
The [model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) describes a
multilingual model under Apache-2.0 with 1024 dimensions and Matryoshka support.
This supports the choice but does not prove quality on our corpus.

| Parameter | Lab contract |
|---|---|
| GGUF repository | `Qwen/Qwen3-Embedding-0.6B-GGUF` |
| Revision | `370f27d7550e0def9b39c1f16d3fbaa13aa67728` |
| File | `Qwen3-Embedding-0.6B-Q8_0.gguf` |
| SHA-256 | `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439` |
| File size | 639150592 bytes; this is not total RAM usage |
| API | `POST /v1/embeddings`, `encoding_format: float` |
| Alias | `qwen3-embedding-0.6b` |
| Pooling | `last` |
| Server response | 1024 numbers per text |
| Lab index | First 256 coordinates, followed by L2 normalization |
| Runtime context | 2048 tokens, one parallel sequence |

The official [GGUF and startup example](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B-GGUF)
confirm the format and pooling method. We limit context for CPU inference; the
model's advertised 32K support does not mean that configuration has been tested
in Codespace. Split long documents into chunks, leaving room for the instruction
and special tokens.

Query: `Instruct: <task description in English>\nQuery:<question>`.
Document: plain text. Do not apply the Nomic prefixes `search_query:` and
`search_document:` to Qwen. Version text preparation along with the index.

## Matryoshka and quantization

Matryoshka learns nested representations: the first part of a vector retains
information useful for retrieval. Our client uses:
`y = x[:256] / sqrt(sum(x[:256] ** 2))`. Apply this equally to queries and
documents; reject zero and non-numeric vectors. Request the full vector rather
than relying on unverified server support for the `dimensions` parameter.

1024 float32 values occupy 4096 bytes; 256 occupy 1024 bytes: four times less
space for the numeric data itself. The index also contains payloads and search
structures. This does not guarantee a fivefold search speedup or a proportional
reduction in embedding computation cost. Original paper:
[Matryoshka Representation Learning](https://arxiv.org/abs/2205.13147).

Q8_0 reduces the size of **model weights**; Matryoshka reduces the length of the
**output vector**. Both choices can affect quality, so evaluate them separately.

## Alternatives

| Option | Decision rationale |
|---|---|
| `nomic-ai/nomic-embed-text-v1.5` | The initial option from the assignment; its model card is tagged English. After clarifying language requirements, we choose a multilingual model. Nomic uses different prefixes, mean pooling, and a different normalization sequence. |
| `intfloat/multilingual-e5-small` | A compact multilingual candidate for future CPU comparisons; do not transfer Qwen's Matryoshka contract to this model. |
| Qwen3-Embedding 4B/8B | Larger options; we do not yet have measurements that justify their resource usage. |
| Ollama | An alternative runtime, not a model. This lab uses the recommended llama.cpp. |

Sources: [Nomic](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5),
[multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small).

## Consequences and acceptance criteria

- Network access is needed to download weights and images; text is processed in Codespace.
- KinD and the model share one machine. Additional workers do not add physical CPU or RAM.
- The measured Codespace has 4 CPUs, 15 GiB RAM, about 8.8 GiB available RAM,
  and only 1.4 GiB free disk space. Free disk capacity must be addressed before
  adding Qwen weights and another runtime image.
- 256 dimensions is the lab candidate; 1024 is the comparison baseline.
- Start with an API smoke check covering three languages. Then evaluate at least
  30 labeled queries, 10 per language, including cross-language retrieval;
  measure Recall@5 and response time.
- Preliminary acceptance criterion for 256: no more than a 5 percentage point
  drop in Recall@5 relative to 1024. Otherwise, retain 1024 and update the ADR.
- Plan a new Qdrant collection, `abox-qwen3-06b-q8-256-v1`, with size 256 and
  distance `Cosine`. Creating and populating it is a subsequent integration step.
- Do not mix models, dimensions, or text preparation methods within one index.
  Evaluate runtime and quantization changes separately; reindex when changing models.

Instructions: [local setup](../todo/TODO-embeddings.md),
[deployment](004-embedding-deployment.md).

## Assignment materials

- [llama-cpp.com](https://llama-cpp.com/) is an unofficial overview; verify commands
  against the [upstream project](https://github.com/ggml-org/llama.cpp).
- [Nomic v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) is a considered alternative.
- The [Matryoshka article](https://medium.com/data-science-collective/matryoshka-embeddings-how-to-make-vector-search-5x-faster-f9fdc54d5ffd)
  is assignment reading; results from another experiment are not measurements for this lab.
