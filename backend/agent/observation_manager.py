import json
from typing import Any, Callable

from loguru import logger

from backend.agent.observation_extractor import extract_observations_from_messages
from backend.data import Database, ObservationRepository, ObservationRecord


class ObservationManager:
    """Standalone manager for extracting and persisting structured observations."""

    def __init__(
        self,
        db: Database | None = None,
        get_provider_and_model: Callable[[], tuple[Any, str, str, int, float]] | None = None,
        record_token_usage: Callable | None = None,
    ):
        self.db = db or Database()
        self._get_provider_and_model = get_provider_and_model
        self._record_token_usage = record_token_usage

    async def extract_from_messages(
        self,
        session_instance_id: int,
        messages: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Extract observations from a list of messages and persist them.
        Returns the list of extracted observation dicts.
        """
        if not messages or len(messages) < 2:
            return []

        if not self._get_provider_and_model:
            logger.warning("ObservationManager: no provider callback configured")
            return []

        try:
            provider, model, provider_type, max_tokens, temperature = self._get_provider_and_model()
            extracted = await extract_observations_from_messages(
                messages=messages,
                provider=provider,
                model=model,
                provider_type=provider_type,
                record_token_usage=self._record_token_usage,
                session_instance_id=session_instance_id,
            )
            if extracted:
                obs_repo = ObservationRepository(self.db)
                for obs in extracted:
                    obs_repo.add_observation(ObservationRecord(
                        session_instance_id=session_instance_id,
                        type=obs.get("type", "general"),
                        title=obs.get("title", ""),
                        narrative=obs.get("narrative", ""),
                        files=obs.get("files", []),
                        concepts=obs.get("concepts", []),
                        token_count=obs.get("token_count", 0),
                    ))
                logger.info(f"ObservationManager: extracted and saved {len(extracted)} observations for instance {session_instance_id}")
            return extracted
        except Exception as e:
            logger.warning(f"ObservationManager extraction failed: {e}")
            return []

    def build_index_markdown(
        self,
        instance_id: int | None = None,
        limit: int = 20,
    ) -> str:
        """Build compact markdown index of observations (for prompt injection)."""
        obs_repo = ObservationRepository(self.db)
        return obs_repo.build_index_markdown(instance_id=instance_id, limit=limit)
