Input:
BGE(sentence)      → 768
BGE(aspect)        → 768
concat             → 1536

Classifier:
LinearSVC(
    C=1.0,
    max_iter=5000
)

Classes:
-1 Negative
 0 Neutral
+1 Positive

Decision:
decision_function()

Threshold:
0.45
