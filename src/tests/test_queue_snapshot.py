import types
import pytest

from cogs.music import Music


class FakeResponse:
    def __init__(self):
        self.messages = []

    async def send_message(self, embed=None, **kwargs):
        self.messages.append((embed, kwargs))


class FakeInteraction:
    def __init__(self, guild_id=1, channel_id=10):
        self.guild = types.SimpleNamespace(id=guild_id, name="Guild")
        self.channel = types.SimpleNamespace(id=channel_id, name="general")
        self.response = FakeResponse()


class FakeIPCClient:
    def __init__(self, state):
        self._state = state

    def update_last_command_channel(self, guild_id, channel_id):
        # no-op for test
        pass

    async def get_player_state(self, guild_id):
        return {"status": "success", "data": {"state": self._state}}


@pytest.mark.asyncio
async def test_queue_snapshot_empty():
    fake_client = FakeIPCClient(state={"queue": []})
    fake_bot = types.SimpleNamespace(ipc_manager=types.SimpleNamespace(ipc_client=fake_client))
    music = Music(fake_bot)

    interaction = FakeInteraction()
    await Music.queue.callback(music, interaction)

    assert len(interaction.response.messages) == 1
    embed, kwargs = interaction.response.messages[0]
    assert embed.title == "🎵 Queue Snapshot"
    assert embed.description == "The queue is currently empty."


@pytest.mark.asyncio
async def test_queue_snapshot_top20_limit():
    # Build 25 songs
    queue = []
    for i in range(25):
        queue.append({
            "title": f"Song {i+1}",
            "duration": 60 + i,
            "requester_name": f"User{i+1}",
            "webpage_url": f"https://youtu.be/video{i+1}"
        })

    fake_client = FakeIPCClient(state={"queue": queue})
    fake_bot = types.SimpleNamespace(ipc_manager=types.SimpleNamespace(ipc_client=fake_client))
    music = Music(fake_bot)

    interaction = FakeInteraction()
    await Music.queue.callback(music, interaction)

    assert len(interaction.response.messages) == 1
    embed, kwargs = interaction.response.messages[0]

    # Ensure only top 20 are shown
    desc = embed.description or ""
    assert "**20.**" in desc
    assert "**21.**" not in desc
    # Footer should mention remaining items (5 more)
    assert embed.footer and embed.footer.text and "5 more" in embed.footer.text


@pytest.mark.asyncio
async def test_queue_snapshot_fewer_no_footer():
    # Build 5 songs
    queue = []
    for i in range(5):
        queue.append({
            "title": f"Song {i+1}",
            "duration": 120 + i,
            "requester_name": f"User{i+1}",
            "webpage_url": f"https://youtu.be/video{i+1}"
        })

    fake_client = FakeIPCClient(state={"queue": queue})
    fake_bot = types.SimpleNamespace(ipc_manager=types.SimpleNamespace(ipc_client=fake_client))
    music = Music(fake_bot)

    interaction = FakeInteraction()
    await Music.queue.callback(music, interaction)

    assert len(interaction.response.messages) == 1
    embed, kwargs = interaction.response.messages[0]

    # Only 5 items, ensure numbering stops at 5 and no 6
    desc = embed.description or ""
    assert "**5.**" in desc
    assert "**6.**" not in desc

    # No footer expected when there are no remaining items
    footer_text = getattr(getattr(embed, "footer", None), "text", None)
    assert not footer_text

