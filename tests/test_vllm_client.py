import json

import httpx

from docsmind.config import Settings
from docsmind.factory import build_llm
from docsmind.llm.vllm_client import VLLMClient


def test_vllm_client_translates_common_contract_to_openai_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.read())
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "  answer [1]  "}}
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    llm = VLLMClient("openclaw", "http://server:11434/v1/", client=client)

    answer = llm.generate("system rules", "user prompt", max_tokens=123)

    assert answer == "answer [1]"
    assert captured["url"] == "http://server:11434/v1/chat/completions"
    body = captured["body"]
    assert body["model"] == "openclaw"
    assert body["max_tokens"] == 123
    assert body["messages"] == [
        {"role": "system", "content": "system rules"},
        {"role": "user", "content": "user prompt"},
    ]


def test_factory_selects_vllm_provider():
    settings = Settings(
        _env_file=None,
        llm_provider="vllm",
        vllm_model="openclaw",
        vllm_base_url="http://localhost:11434/v1",
    )
    llm = build_llm(settings)
    assert isinstance(llm, VLLMClient)
    assert llm.model == "openclaw"
