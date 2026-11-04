import re
from pathlib import Path
from typing import List, Optional, Tuple
import numpy as np


class ReviewAnalysisPipeline:
    def __init__(
        self,
        aspect_joblib_path: Path | str,
        sentiment_joblib_path: Path | str,
        device: Optional[str] = None,
    ):
        import joblib
        from sentence_transformers import SentenceTransformer

        asp_bundle = joblib.load(aspect_joblib_path)
        self.aspect_clf = asp_bundle["classifier"]
        self.aspects = list(asp_bundle["aspects"])
        self.aspect_threshold = float(asp_bundle.get("threshold", -0.25))
        self.aspect_normalize = bool(asp_bundle.get("normalized_embeddings", True))
        aspect_encoder_name = asp_bundle.get("encoder", "BAAI/bge-base-en-v1.5")

        sent_bundle = joblib.load(sentiment_joblib_path)
        self.sentiment_clf = sent_bundle["classifier"]
        self.input_template = sent_bundle.get(
            "input_template", "Aspect: {aspect}. Sentence: {sentence}"
        )
        self.neutral_threshold = float(sent_bundle.get("neutral_threshold", 0.44))
        self.sentiment_classes = np.array(sent_bundle.get("classes", [-1, 0, 1]))
        sentiment_encoder_name = sent_bundle.get(
            "encoder", "sentence-transformers/all-mpnet-base-v2"
        )

        self.aspect_encoder = SentenceTransformer(aspect_encoder_name, device=device)
        self.sentiment_encoder = SentenceTransformer(
            sentiment_encoder_name, device=device
        )

        self.nlp = None
        try:
            import spacy
            try:
                self.nlp = spacy.load("en_core_web_sm", disable=["ner", "tagger", "lemmatizer"])
            except OSError:
                self.nlp = spacy.blank("en")
            if not any(p in self.nlp.pipe_names for p in ("parser", "senter", "sentencizer")):
                self.nlp.add_pipe("sentencizer")
        except ImportError:
            pass

    @staticmethod
    def _regex_split_sentences(text: str) -> list[str]:
        return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text.strip()) if p and p.strip()]

    def split_reviews_into_sentences(self, reviews: list[dict]) -> list[dict]:
        sentences_out = []
        if self.nlp is not None:
            texts = [r["review_text"] for r in reviews]
            for rev, doc in zip(reviews, self.nlp.pipe(texts, batch_size=64)):
                pos = 0
                for sent in doc.sents:
                    s_text = sent.text.strip()
                    if not s_text:
                        continue
                    sentences_out.append(
                        {
                            "review_id": rev["review_id"],
                            "position": pos,
                            "sentence_text": s_text,
                        }
                    )
                    pos += 1
        else:
            for rev in reviews:
                for pos, s_text in enumerate(self._regex_split_sentences(rev["review_text"])):
                    sentences_out.append(
                        {
                            "review_id": rev["review_id"],
                            "position": pos,
                            "sentence_text": s_text,
                        }
                    )
        return sentences_out

    def predict_aspects(self, sentence_texts: list[str], batch_size: int = 64) -> list[list[str]]:
        if not sentence_texts:
            return []
        embeddings = self.aspect_encoder.encode(
            sentence_texts,
            batch_size=batch_size,
            normalize_embeddings=self.aspect_normalize,
            show_progress_bar=False,
        )
        scores = self.aspect_clf.decision_function(embeddings)
        results = []
        for row in scores:
            indices = np.where(row >= self.aspect_threshold)[0]
            results.append([self.aspects[i] for i in indices] if len(indices) else [])
        return results

    def _apply_sentiment_threshold(self, scores: np.ndarray) -> np.ndarray:
        idx_neu = int(np.where(self.sentiment_classes == 0)[0][0])
        preds = np.empty(len(scores), dtype=int)
        for i, s in enumerate(scores):
            if s[idx_neu] >= self.neutral_threshold:
                preds[i] = 0
            else:
                preds[i] = int(self.sentiment_classes[int(np.argmax(s))])
        return preds

    def analyze_sentences(
        self, sentences: list[dict], batch_size: int = 64
    ) -> Tuple[list[dict], list[dict]]:
        if not sentences:
            return [], []
        texts = [s["sentence_text"] for s in sentences]
        aspect_lists = self.predict_aspects(texts, batch_size=batch_size)

        conditioned_inputs = []
        pair_meta = []

        for idx, (sent_info, asp_list) in enumerate(zip(sentences, aspect_lists)):
            sent_info["has_aspects"] = 1 if len(asp_list) > 0 else 0
            for asp in asp_list:
                if asp and asp != "None":
                    #оценка конкретного аспекта(некие проблемы сохраняются, но лучше чем без подстановки)
                    formatted = self.input_template.format(
                        aspect=asp, sentence=sent_info["sentence_text"]
                    )
                    conditioned_inputs.append(formatted)
                    pair_meta.append((idx, asp))

        sentiment_records = []
        if conditioned_inputs:
            sent_embeddings = self.sentiment_encoder.encode(
                conditioned_inputs,
                batch_size=batch_size,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            raw_scores = self.sentiment_clf.decision_function(sent_embeddings)
            pred_labels = self._apply_sentiment_threshold(raw_scores)

            for (sent_idx, asp), label in zip(pair_meta, pred_labels):
                s_info = sentences[sent_idx]
                sentiment_records.append(
                    {
                        "review_id": s_info["review_id"],
                        "position": s_info["position"],
                        "aspect": asp,
                        "sentiment": int(label),
                    }
                )

        return sentences, sentiment_records
