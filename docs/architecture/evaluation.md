# Evaluation architecture

Evaluation has two layers.

## Retrieval evaluation

The golden dataset identifies expected sources. Precision and recall are calculated over retrieved evidence.

## Answer evaluation

Groundedness is evaluated against retrieved evidence. Regression gates prevent silent quality degradation.

The intended CI loop is:

`change → tests → golden evaluation → quality gate → merge`
