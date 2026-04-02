from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB
import numpy as np

class IntentClassifier:
    """A deterministic statistical classifier for Neurosymbolic intent mapping."""

    def __init__(self):
        self.vectorizer = CountVectorizer()
        self.classifier = MultinomialNB()
        self._train_initial_model()

    def _train_initial_model(self):
        """Bootstraps the model with a baseline understanding of the world."""
        # The messy real-world inputs
        training_sentences = [
            "Initiate system diagnostic.",
            "Run a health check.",
            "What is your status?",
            "Scrape the news.",
            "Get the latest headlines from the web.",
            "Read this url for me.",
            "Hello Ana.",
            "Who are you?",
            "Hi there!"
        ]

        # The rigid, symbolic concepts they map to
        training_labels = [
            "intent_diagnostic",
            "intent_diagnostic",
            "intent_diagnostic",
            "intent_scrape",
            "intent_scrape",
            "intent_scrape",
            "intent_greeting",
            "intent_greeting",
            "intent_greeting"
        ]

        # Transform text into a mathematical matrix and train the algorithm
        X_train = self.vectorizer.fit_transform(training_sentences)
        self.classifier.fit(X_train, training_labels)

    def classify(self, text: str) -> dict:
        """Evaluates raw text and returns the predicted symbolic intent and confidence."""
        X_test = self.vectorizer.transform([text])
        prediction = self.classifier.predict(X_test)[0]

        # Get confidence score (probability from 0.0 to 1.0)
        probabilities = self.classifier.predict_proba(X_test)[0]
        max_prob = np.max(probabilities)

        return {
            "intent": prediction,
            "confidence": float(max_prob)
        }
