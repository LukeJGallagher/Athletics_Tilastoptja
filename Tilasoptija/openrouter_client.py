"""
OpenRouter Client for AI-Powered Insights

Provides integration with OpenRouter API for generating narrative insights
about athlete performance, form analysis, and competition predictions.

Uses free models from OpenRouter for cost-effective AI analysis.

Future implementation will include:
- Form narrative generation
- Competition readiness assessment
- Competitor threat analysis
- Strategic recommendations
"""

import os
import json
import requests
from typing import Dict, List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenRouter configuration - primary and backup keys
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_KEY_2 = os.getenv("OPENROUTER_API_KEY_2")  # Backup key
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Free models available on OpenRouter (updated 2025)
FREE_MODELS = [
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-2-9b-it:free",
    "mistralai/mistral-7b-instruct:free",
    "qwen/qwen-2-7b-instruct:free",
    "meta-llama/llama-3-8b-instruct:free",
]

# Default model to use (prioritize newer free models)
DEFAULT_MODEL = "meta-llama/llama-3.2-3b-instruct:free"


class OpenRouterClient:
    """Client for OpenRouter API integration."""

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize OpenRouter client.

        Args:
            api_key: OpenRouter API key (defaults to env variable)
            model: Model to use (defaults to DEFAULT_MODEL)
        """
        self.api_key = api_key or OPENROUTER_API_KEY
        self.model = model or DEFAULT_MODEL
        self.base_url = OPENROUTER_BASE_URL

        if not self.api_key:
            raise ValueError("OpenRouter API key not found. Set OPENROUTER_API_KEY in .env")

    def _make_request(self, messages: List[Dict], max_tokens: int = 500) -> Optional[str]:
        """
        Make a request to OpenRouter API.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens in response

        Returns:
            Response content or None if error
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://athletics-dashboard.streamlit.app",
            "X-Title": "Athletics Dashboard"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7
        }

        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            return data['choices'][0]['message']['content']

        except requests.exceptions.RequestException as e:
            print(f"OpenRouter API error: {e}")
            return None

    def generate_form_insight(self, athlete_data: Dict) -> Optional[str]:
        """
        Generate narrative insight about athlete's form.

        Args:
            athlete_data: Dict with athlete info including:
                - name: Athlete name
                - event: Event name
                - season_best: Current season best
                - personal_best: All-time personal best
                - recent_performances: List of recent results
                - trend: 'improving', 'stable', or 'declining'

        Returns:
            Narrative insight string or None
        """
        prompt = f"""You are an athletics performance analyst. Generate a brief (2-3 sentences)
insight about this athlete's current form for coaches preparing for a major championship.

Athlete: {athlete_data.get('name', 'Unknown')}
Event: {athlete_data.get('event', 'Unknown')}
Season Best: {athlete_data.get('season_best', 'N/A')}
Personal Best: {athlete_data.get('personal_best', 'N/A')}
Recent Performances: {athlete_data.get('recent_performances', [])}
Trend: {athlete_data.get('trend', 'unknown')}

Focus on:
1. Current form trajectory
2. How recent performances compare to their capability
3. One key observation for the coach

Be concise and actionable. Do not use promotional language."""

        messages = [{"role": "user", "content": prompt}]
        return self._make_request(messages, max_tokens=200)

    def generate_competitor_analysis(self, athlete_data: Dict, competitors: List[Dict]) -> Optional[str]:
        """
        Generate analysis of competitive landscape.

        Args:
            athlete_data: Dict with athlete info
            competitors: List of competitor dicts

        Returns:
            Competitive analysis string or None
        """
        prompt = f"""You are an athletics performance analyst. Generate a brief competitive
assessment for a coach preparing an athlete for a major championship.

Your Athlete: {athlete_data.get('name', 'Unknown')}
Event: {athlete_data.get('event', 'Unknown')}
Season Best: {athlete_data.get('season_best', 'N/A')}

Top Competitors:
{json.dumps(competitors[:5], indent=2)}

Provide:
1. One sentence on competitive position
2. One key rival to watch
3. One tactical observation

Be concise and practical. Maximum 4 sentences."""

        messages = [{"role": "user", "content": prompt}]
        return self._make_request(messages, max_tokens=250)

    def generate_championship_readiness(
        self,
        athlete_data: Dict,
        benchmarks: Dict,
        probabilities: Dict
    ) -> Optional[str]:
        """
        Generate championship readiness assessment.

        Args:
            athlete_data: Athlete information
            benchmarks: Medal/final/semi/heat benchmarks
            probabilities: Advancement probabilities

        Returns:
            Readiness assessment string or None
        """
        prompt = f"""You are an athletics performance analyst. Generate a championship
readiness assessment for a coach.

Athlete: {athlete_data.get('name', 'Unknown')}
Event: {athlete_data.get('event', 'Unknown')}
Projected Performance: {athlete_data.get('projected', 'N/A')}

Championship Benchmarks:
- Medal line: {benchmarks.get('medal', 'N/A')}
- Final line: {benchmarks.get('final', 'N/A')}
- Semi line: {benchmarks.get('semi', 'N/A')}
- Heat survival: {benchmarks.get('heat', 'N/A')}

Advancement Probabilities:
- Make finals: {probabilities.get('final', 'N/A')}%
- Win medal: {probabilities.get('medal', 'N/A')}%

Provide a 3-sentence assessment covering:
1. Realistic expectations for this championship
2. Primary goal recommendation
3. One preparation focus

Be honest and practical. Avoid overly optimistic language."""

        messages = [{"role": "user", "content": prompt}]
        return self._make_request(messages, max_tokens=200)


def get_ai_insight(athlete_data: Dict, insight_type: str = 'form') -> Optional[str]:
    """
    Convenience function to get AI insight.

    Args:
        athlete_data: Athlete data dictionary
        insight_type: 'form', 'competitor', or 'readiness'

    Returns:
        AI-generated insight or fallback message
    """
    try:
        client = OpenRouterClient()

        if insight_type == 'form':
            return client.generate_form_insight(athlete_data)
        elif insight_type == 'competitor':
            competitors = athlete_data.get('competitors', [])
            return client.generate_competitor_analysis(athlete_data, competitors)
        elif insight_type == 'readiness':
            benchmarks = athlete_data.get('benchmarks', {})
            probabilities = athlete_data.get('probabilities', {})
            return client.generate_championship_readiness(
                athlete_data, benchmarks, probabilities
            )
        else:
            return None

    except Exception as e:
        print(f"AI insight generation failed: {e}")
        return None


# Placeholder insights for when AI is unavailable
FALLBACK_INSIGHTS = {
    'form': "Form analysis based on statistical projections. AI narrative insights available with OpenRouter integration.",
    'competitor': "Competitive analysis based on season best comparisons. AI-powered insights coming soon.",
    'readiness': "Readiness assessment based on historical championship benchmarks."
}


def get_insight_or_fallback(athlete_data: Dict, insight_type: str = 'form') -> str:
    """
    Get AI insight with fallback to static message.

    Args:
        athlete_data: Athlete data dictionary
        insight_type: Type of insight requested

    Returns:
        AI insight or fallback message
    """
    # Check if API key is configured
    if not OPENROUTER_API_KEY:
        return FALLBACK_INSIGHTS.get(insight_type, "Insight unavailable.")

    # Try to get AI insight
    insight = get_ai_insight(athlete_data, insight_type)

    if insight:
        return insight

    return FALLBACK_INSIGHTS.get(insight_type, "Insight unavailable.")


# Module-level test
if __name__ == "__main__":
    # Test the client
    test_athlete = {
        'name': 'Mohammed Al-Yousef',
        'event': '400m',
        'season_best': 44.72,
        'personal_best': 44.51,
        'recent_performances': [44.72, 44.89, 45.01, 45.15],
        'trend': 'improving'
    }

    print("Testing OpenRouter client...")

    if OPENROUTER_API_KEY:
        insight = get_ai_insight(test_athlete, 'form')
        print(f"\nAI Insight:\n{insight}")
    else:
        print("No API key configured. Using fallback.")
        print(f"\nFallback: {get_insight_or_fallback(test_athlete, 'form')}")
