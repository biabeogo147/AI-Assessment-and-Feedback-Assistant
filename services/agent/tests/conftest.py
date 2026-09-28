"""No test in this directory is allowed to reach a model provider.

A test that calls a real model is slow, costs money, and answers differently
every run, so it can only assert vague things -- exactly the kind of test that
passes while the thing it guards is broken. The seam is `agent.llm`, and this
fixture closes it for the whole suite rather than leaving each test to remember.

`agent/llm.py` is the only module that builds a provider client, so replacing
`chat_models` here is enough: the handlers ask `with_fallback` for a runnable
and never learn whose it is.
"""

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

from agent import llm


@pytest.fixture(autouse=True)
def no_real_model(monkeypatch: pytest.MonkeyPatch) -> GenericFakeChatModel:
    """Give every test a fake chat model in place of a provider client.

    Args:
        monkeypatch: pytest's patcher, scoped to one test.

    Returns:
        The fake, so a test that cares can read what was asked of it or queue
        a different answer.

    Side effects:
        Replaces `agent.llm.chat_models` for the duration of the test and
        clears its cache on the way in, so a real client built by an earlier
        test cannot leak across.
    """
    fake = GenericFakeChatModel(messages=iter(["nội dung giả cho test"] * 1000))
    llm.chat_models.cache_clear()
    monkeypatch.setattr(llm, "chat_models", lambda: (fake,))
    return fake
