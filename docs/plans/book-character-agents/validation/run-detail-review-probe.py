"""Two fixed native reviews of a captured development failure, without publication."""

import asyncio
import copy
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


async def main() -> None:
    sys.path.insert(0, str(REPO))
    from backend.services.book_world.chat_models import REVIEW_PROMPTS, ChatCandidate, ChatReview
    from backend.services.book_world.chat_provider import resolve_character_chat_model
    from backend.services.book_world.chat_validation import SemanticReviewError, validate_review
    from backend.services.book_world.discovery import _json
    from backend.services.book_world.knowledge import CharacterKnowledgeService
    from backend.services.book_world.knowledge_models import CanonicalScope
    from backend.services.book_world.storage import connect

    original = Path(__file__).with_name("detail-review-input.json")
    output = Path(__file__).with_name("real-model-detail-review-v7.json")
    trace = REPO / "tmp/detail-review-v7-calls.json"
    if output.exists() or trace.exists():
        raise RuntimeError("Probe already exists; inspect its live handle or terminal result")
    recorded = json.loads(original.read_text(encoding="utf-8"))
    context = recorded["context"]
    actor = CanonicalScope.model_validate(context["character_scope"])
    service = CharacterKnowledgeService(REPO / "tmp/book-corpus-workspace")
    with connect(service.db_path) as database:
        service.validate_scope(database, actor)
    candidate = ChatCandidate.model_validate(recorded["candidate"])
    corrected = copy.deepcopy(candidate.model_dump())
    corrected["content"] = corrected["content"].replace("，那时群猴还在外头看", "")
    corrected["claims"][0]["text"] = corrected["claims"][0]["text"].replace(
        "，那时群猴还在外头看", ""
    )
    cases = [
        ("unsupported_observer_detail", candidate, False),
        ("grounded_event_and_new_hypothesis", ChatCandidate.model_validate(corrected), True),
    ]
    model = resolve_character_chat_model(2, 337)
    config = model.config.model_copy(update={
        "prompt_version": "character-chat-v11",
        "review_prompt_version": "character-chat-review-v7",
    })
    report = {
        "scope": "Frozen development replay through native review; not full-book acceptance",
        "native_call_budget": 2,
        "source_sha256": hashlib.sha256(original.read_bytes()).hexdigest(),
        "model_config": config.model_dump(),
        "publication": False,
        "quality_pass": False,
        "calls": [],
    }
    raw = []

    def save() -> None:
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        trace.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save()
    for case_id, reply, expected_support in cases:
        payload = {
            "phase": "review",
            "context": context,
            "candidate": reply.model_dump(exclude={"claims"}),
            "review_claims": [
                {"ordinal": ordinal, "assertion": assertion.model_dump()}
                for ordinal, assertion in enumerate(reply.claims)
            ],
            "feedback": None,
        }
        prompt = REVIEW_PROMPTS[config.review_prompt_version]
        messages = [
            {"role": "system", "content": prompt + _json(ChatReview.model_json_schema())},
            {"role": "user", "content": _json(payload)},
        ]
        call = {
            "case_id": case_id,
            "expected_support": expected_support,
            "input_sha256": hashlib.sha256(_json(messages).encode()).hexdigest(),
            "status": "started",
        }
        report["calls"].append(call)
        capture = {"input": payload}
        raw.append(capture)
        save()
        started = time.monotonic()
        try:
            response = await asyncio.wait_for(
                model.provider.chat(
                    messages,
                    model=model.config.model,
                    max_tokens=model.config.max_tokens,
                    temperature=0,
                    reasoning_effort=model.config.reasoning_effort,
                ),
                timeout=model.config.call_timeout_seconds,
            )
            capture["content"] = response.content
            call.update(status="completed", finish_reason=response.finish_reason, usage=response.usage)
            if response.finish_reason not in ("stop", "end_turn") or response.tool_calls:
                raise ValueError("Review response is incomplete")
            try:
                review = validate_review(reply, response.content)
                supported = True
                call["review"] = review.model_dump()
            except SemanticReviewError as error:
                supported = False
                call["rejection"] = error.feedback
            call.update(actual_support=supported, expectation_met=supported == expected_support)
        except Exception as error:
            call.update(expectation_met=False, error_type=type(error).__name__, error=str(error)[:300])
        finally:
            call["elapsed_seconds"] = round(time.monotonic() - started, 3)
            save()
            print(json.dumps(call, ensure_ascii=False), flush=True)
    report.update(terminal=True, actual_calls=len(raw))
    save()


if __name__ == "__main__":
    asyncio.run(main())
