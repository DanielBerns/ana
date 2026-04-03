import re
from sklearn.feature_extraction.text import TfidfVectorizer

class FactExtractor:
    """A deterministic NLP engine for extracting symbolic concepts from raw text."""

    def __init__(self):
        # We configure the vectorizer to ignore common English stop words
        # and only return the top 5 most statistically significant terms.
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=5)

    def clean_html(self, raw_html: str) -> str:
        """Strips HTML tags to isolate the raw textual data."""
        cleanr = re.compile('<.*?>')
        cleantext = re.sub(cleanr, ' ', raw_html)
        # Remove extra whitespace
        return re.sub(r'\s+', ' ', cleantext).strip()

    def extract_keywords(self, text: str) -> list[str]:
        """Calculates the TF-IDF matrix and extracts the top symbolic entities."""
        try:
            # Fit and transform the single document
            self.vectorizer.fit_transform([text])

            # Retrieve the statistically significant keywords
            feature_names = self.vectorizer.get_feature_names_out()
            return list(feature_names)
        except ValueError:
            # Fallback if the text is empty or too short
            return []
