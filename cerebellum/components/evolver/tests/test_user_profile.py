import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
from evolver.models import Memory
from evolver.user_profile import UserProfile, ProfileTrait


class TestProfileTrait:
    def test_create_static_trait(self):
        trait = ProfileTrait(
            key="language", value="TypeScript", source="explicit", is_static=True
        )
        assert trait.key == "language"
        assert trait.value == "TypeScript"
        assert trait.is_static is True

    def test_create_dynamic_trait(self):
        trait = ProfileTrait(
            key="current_task", value="API integration", source="inferred", is_static=False
        )
        assert trait.is_static is False

    def test_trait_is_expired_static_never(self):
        trait = ProfileTrait(
            key="language", value="TypeScript", source="explicit",
            is_static=True,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.0,
        )
        assert trait.is_expired() is False

    def test_trait_is_expired_dynamic_with_decay(self):
        old_time = datetime.now(timezone.utc) - timedelta(days=90)
        trait = ProfileTrait(
            key="current_task", value="old task", source="inferred",
            is_static=False,
            created_at=old_time,
            last_accessed=old_time,
            decay_rate=0.05,
        )
        assert trait.is_expired() is True

    def test_trait_is_expired_dynamic_recent(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=1)
        trait = ProfileTrait(
            key="current_task", value="new task", source="inferred",
            is_static=False,
            created_at=recent,
            last_accessed=recent,
            decay_rate=0.05,
        )
        assert trait.is_expired() is False

    def test_update_access_refreshes_timestamp(self):
        trait = ProfileTrait(
            key="test", value="v", source="s", is_static=False,
            last_accessed=datetime.now(timezone.utc) - timedelta(days=30),
        )
        old_access = trait.last_accessed
        trait.update_access()
        assert trait.last_accessed > old_access


class TestUserProfile:
    def test_empty_profile(self):
        profile = UserProfile()
        prompt = profile.to_prompt()
        assert "user profile" in prompt.lower() or "profile" in prompt.lower()

    def test_add_static_trait(self):
        profile = UserProfile()
        profile.add_static("language", "TypeScript", source="explicit")
        assert "language" in profile.static
        assert profile.static["language"].value == "TypeScript"

    def test_add_dynamic_trait(self):
        profile = UserProfile()
        profile.add_dynamic("current_task", "API integration", source="inferred")
        assert "current_task" in profile.dynamic
        assert profile.dynamic["current_task"].value == "API integration"

    def test_to_prompt_includes_static(self):
        profile = UserProfile()
        profile.add_static("language", "TypeScript")
        prompt = profile.to_prompt()
        assert "TypeScript" in prompt
        assert "language" in prompt.lower()

    def test_to_prompt_includes_dynamic(self):
        profile = UserProfile()
        profile.add_dynamic("current_project", "Evolver v2")
        prompt = profile.to_prompt()
        assert "Evolver v2" in prompt

    def test_to_prompt_excludes_expired(self):
        profile = UserProfile()
        old_time = datetime.now(timezone.utc) - timedelta(days=90)
        trait = ProfileTrait(
            key="old_task", value="expired task", source="inferred",
            is_static=False, created_at=old_time, last_accessed=old_time,
            decay_rate=0.05,
        )
        profile.dynamic["old_task"] = trait
        prompt = profile.to_prompt()
        assert "expired task" not in prompt

    def test_from_memories_extracts_preferences(self):
        profile = UserProfile()
        mock_storage = MagicMock()
        memories = [
            Memory(id=1, content="I prefer TypeScript over JavaScript", category="success",
                  tags=["typescript", "preference"]),
            Memory(id=2, content="Always use Docker for deployment", category="insight",
                  tags=["docker", "deployment"]),
        ]
        mock_storage.get_all_memories_columns.return_value = memories
        profile.from_memories(mock_storage)
        assert len(profile.static) > 0 or len(profile.dynamic) > 0

    def test_from_memories_empty(self):
        profile = UserProfile()
        mock_storage = MagicMock()
        mock_storage.get_all_memories_columns.return_value = []
        profile.from_memories(mock_storage)
        assert len(profile.static) == 0
        assert len(profile.dynamic) == 0

    def test_remove_expired_dynamic_traits(self):
        profile = UserProfile()
        old_time = datetime.now(timezone.utc) - timedelta(days=90)
        profile.dynamic["expired"] = ProfileTrait(
            key="expired", value="gone", source="inferred",
            is_static=False, created_at=old_time, last_accessed=old_time,
            decay_rate=0.05,
        )
        profile.dynamic["active"] = ProfileTrait(
            key="active", value="here", source="inferred",
            is_static=False,
            created_at=datetime.now(timezone.utc),
            last_accessed=datetime.now(timezone.utc),
            decay_rate=0.01,
        )
        removed = profile.remove_expired()
        assert removed == 1
        assert "expired" not in profile.dynamic
        assert "active" in profile.dynamic

    def test_static_traits_not_removed_by_expired(self):
        profile = UserProfile()
        profile.add_static("language", "TypeScript")
        removed = profile.remove_expired()
        assert removed == 0
        assert "language" in profile.static