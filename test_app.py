"""
Automated Test Suite for DocuMind Local RAG Assistant
Run this script locally to verify your application before pushing to GitHub:
    python test_app.py
"""

import sys
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rag_engine import (
    extract_youtube_video_id,
    format_timestamp,
    is_simple_greeting,
    GUARDRAIL_REFUSAL_MSG,
    stream_rag_chat
)
from app.config import get_public_settings


class TestDocuMind(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_check(self):
        """Test API health endpoint"""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "healthy")

    def test_get_config(self):
        """Test configuration endpoint returns masked keys and settings"""
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("keys_configured", data)
        self.assertIn("masked_keys", data)
        self.assertIn("strict_guardrails", data)

    def test_youtube_video_id_extraction(self):
        """Test parsing various formats of YouTube URLs"""
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        for url, expected_id in test_cases:
            with self.subTest(url=url):
                self.assertEqual(extract_youtube_video_id(url), expected_id)

    def test_format_timestamp(self):
        """Test timestamp formatting into [MM:SS]"""
        self.assertEqual(format_timestamp(0), "00:00")
        self.assertEqual(format_timestamp(65), "01:05")
        self.assertEqual(format_timestamp(3665), "01:01:05")

    def test_greeting_guardrail_detection(self):
        """Test simple greetings trigger pleasant greeting responses"""
        self.assertTrue(is_simple_greeting("hello"))
        self.assertTrue(is_simple_greeting("Hi!"))
        self.assertTrue(is_simple_greeting("Good morning"))
        self.assertFalse(is_simple_greeting("What is this video about?"))
        self.assertFalse(is_simple_greeting("Explain quantum computing"))

    def test_strict_guardrail_blocking_empty_vault(self):
        """Test that strict guardrails block off-topic queries when guardrails are enabled"""
        import json
        response = self.client.post(
            "/api/chat/stream",
            json={
                "message": "Who was the first president of the United States?",
                "use_rag": True,
                "strict_guardrails": True
            }
        )
        self.assertEqual(response.status_code, 200)
        accumulated = ""
        for line in response.text.split("\n\n"):
            if line.startswith("data: "):
                try:
                    payload = json.loads(line[6:].strip())
                    if payload.get("type") == "token":
                        accumulated += payload.get("content", "")
                except Exception:
                    pass
        # Must contain guardrail notice or scope refusal
        self.assertTrue("Guardrail Notice" in accumulated or "outside the scope" in accumulated)

    def test_static_index_serving(self):
        """Test root serves HTML application"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("DocuMind", response.text)


if __name__ == "__main__":
    print("=" * 60)
    print("  Running DocuMind Pre-Push Verification Suite...")
    print("=" * 60)
    unittest.main(verbosity=2)
