import pytest

from src.mcps.web_fetch import web_fetch

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/Artificial_intelligence"


@pytest.mark.integration
async def test_fetch_wikipedia():
    result = await web_fetch(WIKIPEDIA_URL)

    assert result["success"] is True
    assert result["url"] == WIKIPEDIA_URL
    print(result["content"])
