Encoder:
BAAI/bge-base-en-v1.5

Embedding:
768
normalized

Classifier:
OneVsRestClassifier(
    LinearSVC(
        C=1.0,
        max_iter=5000
    )
)

Aspect threshold:
-0.25

Classes:
15 aspects

None:
if no aspect score >= -0.25
