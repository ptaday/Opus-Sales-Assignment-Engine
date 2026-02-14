"""Live Anthropic API test. Run only when ANTHROPIC_API_KEY is set."""
import os
import pytest

pytestmark = pytest.mark.api


def test_anthropic_messages_create_live():
    """One messages.create call returns 200 and non-empty content (live)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    try:
        import anthropic
    except ImportError:
        pytest.skip("anthropic package not installed")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-3-5-haiku-20241022",
        max_tokens=64,
        messages=[{"role": "user", "content": "Reply with one word: OK"}],
    )
    assert message.content
    assert message.content[0].text
    assert len(message.content[0].text.strip()) > 0
