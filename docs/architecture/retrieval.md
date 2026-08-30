# Retrieval architecture

Knowledge Fabric uses multiple retrieval signals:

1. lexical matching
2. local vector similarity
3. symbol-aware matching for code
4. reciprocal-rank fusion
5. optional second-stage reranking
6. corrective retrieval when evidence is weak

The goal is not to maximize one score. The goal is to return diverse, relevant evidence that can support a grounded answer.
