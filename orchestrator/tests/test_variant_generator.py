"""
Tests for the variant generator module.

Validates that VariantGenerator correctly:
- Calls Claude Haiku with the right prompts
- Returns exactly N parsed variant dicts
- Includes all required fields in each variant
- Handles custom demographics
- Passes previous iteration results through to the prompt
"""

import pytest
from unittest.mock import AsyncMock, patch

from orchestrator.engine.variant_generator import VariantGenerator


# -- Sample data --

MOCK_HAIKU_RESPONSE = {
    "variants": [
        {
            "id": "v1_social_proof",
            "content": "Join thousands of professionals who already trust our platform.",
            "strategy": "Social proof approach leveraging peer validation",
            "key_psychological_mechanisms": ["social proof", "bandwagon effect"],
            "expected_strengths": ["builds trust", "reduces perceived risk"],
            "potential_risks": ["may feel impersonal"],
        },
        {
            "id": "v2_fear_reduction",
            "content": "Stop worrying about data security. Our system handles it.",
            "strategy": "Fear reduction through reassurance messaging",
            "key_psychological_mechanisms": ["threat mitigation", "anxiety reduction"],
            "expected_strengths": ["addresses pain point", "calming tone"],
            "potential_risks": ["could highlight fears instead of reducing them"],
        },
    ]
}


@pytest.fixture
def mock_claude():
    """Create a mock ClaudeClient that returns sample variants."""
    client = AsyncMock()
    client.call_haiku_json.return_value = MOCK_HAIKU_RESPONSE
    return client


@pytest.fixture
def generator(mock_claude):
    """Create a VariantGenerator with a mocked Claude client."""
    return VariantGenerator(claude_client=mock_claude)


# -- Test 1: Returns exactly N variants --

@pytest.mark.asyncio
async def test_generate_variants_returns_exactly_2(generator, mock_claude):
    """generate_variants returns exactly 2 variant dicts when num_variants=2."""
    variants = await generator.generate_variants(
        campaign_brief="Launch our new AI-powered analytics platform for enterprise teams.",
        demographic="tech_professionals",
        num_variants=2,
    )
    assert len(variants) == 2
    mock_claude.call_haiku_json.assert_called_once()


# -- Test 2: Each variant has all required keys --

@pytest.mark.asyncio
async def test_variant_has_required_keys(generator):
    """Each variant dict has keys: id, content, strategy, key_psychological_mechanisms,
    expected_strengths, potential_risks."""
    variants = await generator.generate_variants(
        campaign_brief="Launch our new AI-powered analytics platform.",
        demographic="tech_professionals",
    )
    required_keys = {
        "id", "content", "strategy",
        "key_psychological_mechanisms", "expected_strengths", "potential_risks",
    }
    for v in variants:
        assert set(v.keys()) == required_keys, (
            f"Variant {v.get('id')} missing keys: {required_keys - set(v.keys())}"
        )


# -- Test 3: Variant IDs follow the pattern v{N}_{slug} --

@pytest.mark.asyncio
async def test_variant_ids_follow_pattern(generator):
    """Variant IDs follow the pattern v{N}_{slug} (e.g., 'v1_social_proof')."""
    import re
    variants = await generator.generate_variants(
        campaign_brief="Test campaign brief for ID pattern validation.",
        demographic="tech_professionals",
    )
    pattern = re.compile(r"^v\d+_[a-z_]+$")
    for v in variants:
        assert pattern.match(v["id"]), (
            f"Variant ID '{v['id']}' does not match pattern v{{N}}_{{slug}}"
        )


# -- Test 4: Previous iteration results included in prompt --

@pytest.mark.asyncio
async def test_previous_iteration_results_in_prompt(generator, mock_claude):
    """When previous_iteration_results is provided, the prompt includes
    'Previous iteration results' section."""
    prev_results = [
        {
            "variant_id": "v1_social_proof",
            "strategy": "Social proof",
            "composite_scores": {"attention_score": 72.0},
            "tribe_scores": {"attention_capture": 70.0},
            "mirofish_metrics": {"organic_shares": 12},
            "iteration_note": "Strong attention but weak virality.",
        }
    ]
    await generator.generate_variants(
        campaign_brief="Test campaign brief.",
        demographic="tech_professionals",
        previous_iteration_results=prev_results,
    )
    # Verify the prompt passed to call_haiku_json contains iteration results
    call_args = mock_claude.call_haiku_json.call_args
    user_prompt = call_args.kwargs.get("user") or call_args[1].get("user") or call_args[0][1]
    assert "Previous iteration results" in user_prompt


# -- Test 5: Custom demographic description is passed through --

@pytest.mark.asyncio
async def test_custom_demographic_passed_through(generator, mock_claude):
    """Custom demographic description is passed through to the prompt correctly."""
    await generator.generate_variants(
        campaign_brief="Test campaign brief for custom demo.",
        demographic="custom",
        demographic_custom="Young parents aged 28-35 in suburban areas",
    )
    call_args = mock_claude.call_haiku_json.call_args
    user_prompt = call_args.kwargs.get("user") or call_args[1].get("user") or call_args[0][1]
    assert "Young parents aged 28-35 in suburban areas" in user_prompt


# -- Test 6: Word limit enforcement --

@pytest.mark.asyncio
async def test_variant_content_truncated_at_word_limit(mock_claude):
    """Variants exceeding 150 words are truncated at the nearest sentence boundary."""
    long_content = " ".join(["word"] * 200) + ". Final sentence."
    mock_claude.call_haiku_json.return_value = {
        "variants": [
            {
                "id": "v1_test",
                "content": long_content,
                "strategy": "test",
                "key_psychological_mechanisms": [],
                "expected_strengths": [],
                "potential_risks": [],
            },
            {
                "id": "v2_short",
                "content": "Short variant under the limit.",
                "strategy": "test",
                "key_psychological_mechanisms": [],
                "expected_strengths": [],
                "potential_risks": [],
            },
        ]
    }
    gen = VariantGenerator(claude_client=mock_claude)
    variants = await gen.generate_variants(
        campaign_brief="Test brief.",
        demographic="tech_professionals",
        num_variants=2,
    )
    assert len(variants[0]["content"].split()) <= 150
    assert variants[1]["content"] == "Short variant under the limit."
