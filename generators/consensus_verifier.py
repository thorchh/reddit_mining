#!/usr/bin/env python3
"""
Consensus Verifier: Validates VLM responses against Reddit consensus

Uses an LLM judge to determine if the VLM's response aligns with the
accepted correct answer from Reddit's top comment.
"""

import json
import os
import time
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env.local'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    print("OpenAI library not installed. Install with: pip install openai")
    OpenAI = None


class ConsensusVerifier:
    """Verify VLM responses against Reddit consensus answers."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the consensus verifier.

        Args:
            api_key: OpenAI API key (or set OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o for quality)
        """
        if OpenAI is None:
            raise ImportError("OpenAI library required. Install with: pip install openai")

        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key")

        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.total_cost = 0.0
        self.request_count = 0
        self.min_request_interval = 0.2  # 200ms between requests

    def build_verification_prompt(self, post_data: Dict[str, Any], vlm_response: str) -> str:
        """
        Build prompt for LLM to verify VLM response correctness.

        Args:
            post_data: Dictionary containing post details and correct answer
            vlm_response: The VLM's response to verify

        Returns:
            Formatted prompt for verification
        """
        title = post_data['title']
        selftext = post_data.get('selftext', '')
        subreddit = post_data['subreddit']
        category = post_data['category']

        # Extract correct answer (top comment)
        top_comment = post_data.get('top_comment', {})
        correct_answer = top_comment.get('comment_text', '')

        prompt = f"""You are evaluating whether a VLM (Vision-Language Model) provided a correct answer.

POST CONTEXT:
- Title: {title}
- Context: {selftext if selftext else "(No additional text)"}
- Domain: r/{subreddit}
- Category: {category}

REDDIT CONSENSUS (Correct Answer):
{correct_answer}

VLM RESPONSE TO EVALUATE:
{vlm_response}

YOUR TASK:
Determine if the VLM's response is factually correct based on the Reddit consensus answer.

EVALUATION CRITERIA:
1. CORRECT: VLM identifies the same answer as Reddit consensus (or a scientifically equivalent term)
2. INCORRECT: VLM provides a different diagnosis/identification
3. UNCERTAIN: VLM hedges, refuses to answer, or provides multiple possibilities without committing
4. PARTIAL: VLM mentions the correct answer but also suggests other possibilities

Consider domain-specific terminology:
- Medical: Different terms for same condition (e.g., "tinea" vs "ringworm")
- Identification: Scientific names vs common names (e.g., "Coccinellidae" vs "ladybug")

OUTPUT FORMAT (JSON):
{{
  "verdict": "CORRECT" | "INCORRECT" | "UNCERTAIN" | "PARTIAL",
  "confidence": 0.0-1.0,
  "explanation": "Brief explanation of your assessment (1-2 sentences)",
  "vlm_answer": "What the VLM identified (if applicable)",
  "matches_consensus": true | false
}}

Important: Focus on factual correctness, not style or detail level."""

        return prompt

    def verify(self, post_data: Dict[str, Any], vlm_response: str) -> Dict[str, Any]:
        """
        Verify if VLM response is correct.

        Args:
            post_data: Post data with correct answer
            vlm_response: VLM's response to verify

        Returns:
            Dictionary with verification results and metadata
        """
        # Rate limiting
        time.sleep(self.min_request_interval)

        verification_prompt = self.build_verification_prompt(post_data, vlm_response)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert evaluator assessing AI model responses for correctness. You provide objective, evidence-based assessments."
                    },
                    {
                        "role": "user",
                        "content": verification_prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for more consistent evaluation
                response_format={"type": "json_object"},
                max_tokens=300
            )

            # Parse response
            result = json.loads(response.choices[0].message.content)

            # Track costs (GPT-4o pricing: $2.50/1M input, $10/1M output)
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            cost = (input_tokens / 1_000_000 * 2.50) + (output_tokens / 1_000_000 * 10.00)
            self.total_cost += cost
            self.request_count += 1

            # Add metadata
            result['cost_usd'] = cost
            result['tokens'] = {
                'input': input_tokens,
                'output': output_tokens
            }
            result['timestamp'] = datetime.utcnow().isoformat() + 'Z'

            return result

        except Exception as e:
            print(f"ERROR verifying response for post {post_data.get('post_id', 'unknown')}: {str(e)}", flush=True)
            import traceback
            traceback.print_exc()
            return {
                'verdict': 'ERROR',
                'confidence': 0.0,
                'explanation': f'Error: {str(e)}',
                'vlm_answer': '',
                'matches_consensus': False,
                'cost_usd': 0.0,
                'tokens': {'input': 0, 'output': 0},
                'error': str(e)
            }

    def get_cost_estimate(self, num_posts: int) -> Dict[str, Any]:
        """Estimate cost for verification."""
        # Average tokens: ~700 input (prompt + responses), ~150 output (verification)
        avg_input_tokens = 700
        avg_output_tokens = 150

        total_input_tokens = num_posts * avg_input_tokens
        total_output_tokens = num_posts * avg_output_tokens

        # GPT-4o pricing: $2.50/1M input, $10/1M output
        input_cost = total_input_tokens / 1_000_000 * 2.50
        output_cost = total_output_tokens / 1_000_000 * 10.00
        total_cost = input_cost + output_cost

        return {
            'num_posts': num_posts,
            'estimated_input_tokens': total_input_tokens,
            'estimated_output_tokens': total_output_tokens,
            'estimated_total_cost': total_cost
        }
