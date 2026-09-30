# Lab 5: Agent Memory Corpus

This directory contains an original small corpus about English-language films
from the 1990s and 2000s. It is designed for indexing in xray-memory: the
`document` field is the text used for embeddings, while `metadata` provides
filters and result attributes.

`corpus/movies-90s-2000s.json` contains 20 documents.  
`corpus/movies-90s-2000s.catalog.json` is the same corpus in xray-memory's
native `servicemap` catalog format; use this file to build a snapshot.
`evaluation/movie-retrieval-cases.json` contains 10 evaluation queries with
expected documents. Do not ingest the evaluation file into memory.

The corpus is for educational use, has no secrets, and is not a copy of a
ready-made dataset. During ingestion, send each `document` to xray-memory with
its matching `metadata` object.
