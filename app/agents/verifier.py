import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class Verifier:
    """
    Deterministic output cleaner that normalizes whitespace and extracts 
    the first sentence.
    
    Note: This implementation intentionally uses simple heuristics 
    (first period) rather than NLP for speed and determinism. It does not 
    handle abbreviations (Dr., Mr., etc.) gracefully by design.
    """
    
    # Regex to match sentence-ending punctuation followed by space or end of string
    SENTENCE_END_PATTERN = re.compile(r'([.!?])(\s+|$)')
    DEFAULT_TRUNCATION_MARKER = "."
    
    def verify(self, question: str, answer: Optional[str]) -> str:
        """
        Clean and verify the answer text.
        
        Args:
            question: Original question (unused, kept for interface compatibility)
            answer: Raw answer text to clean. None or empty returns empty string.
            
        Returns:
            Cleaned single sentence with normalized whitespace.
        """
        if not answer:
            return ""
        
        # Normalize whitespace (tabs, newlines, multiple spaces -> single space)
        normalized = self._normalize_whitespace(answer)
        
        # Extract first sentence
        cleaned = self._extract_first_sentence(normalized)
        
        logger.debug(f"Verified {len(answer)} chars -> {len(cleaned)} chars")
        return cleaned
    
    def _normalize_whitespace(self, text: str) -> str:
        """
        Collapse all whitespace sequences into single spaces.
        
        Args:
            text: Raw text with potential irregular spacing
            
        Returns:
            Text with normalized spacing
        """
        # split() without arguments splits on any whitespace and discards empty strings
        return " ".join(text.split())
    
    def _extract_first_sentence(self, text: str) -> str:
        """
        Extract the first sentence using the first period as delimiter.
        
        Note: This is intentionally naive and does not handle 
        abbreviations (e.g., "Dr.", "U.S.A.") or multiple punctuation 
        marks sophisticatedly.
        
        Args:
            text: Whitespace-normalized text
            
        Returns:
            First sentence including its terminating period, 
            or full text if no period found
        """
        match = self.SENTENCE_END_PATTERN.search(text)
        
        if not match:
            # No sentence-ending punctuation found, return as-is
            return text.strip()
        
        # Extract up to and including the punctuation mark
        end_pos = match.end(1)  # Position after the punctuation mark
        first_sentence = text[:end_pos].strip()
        
        return first_sentence