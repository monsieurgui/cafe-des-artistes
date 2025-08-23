import types
import pytest

from utils.ipc_client import IPCClient


class FakeMessage:
    _next_id = 100

    def __init__(self, embed):
        self.id = FakeMessage._next_id
        FakeMessage._next_id += 1
        self.embed = embed
        self.deleted = False

    async def delete(self):
        self.deleted = True


class FakeChannel:
    def __init__(self, channel_id=10):
        self.id = channel_id
        self.messages = []

    async def send(self, embed=None, **kwargs):
        msg = FakeMessage(embed)
        self.messages.append(msg)
        return msg

    async def fetch_message(self, message_id: int):
        for m in self.messages:
            if m.id == message_id:
                return m
        # Fallback: return a dummy message (delete shouldn't be called in this path)
        return FakeMessage(None)


class FakeBot:
    def __init__(self, channel: FakeChannel):
        self._channel = channel

    def get_channel(self, channel_id: int):
        if channel_id == self._channel.id:
            return self._channel
        return None


@pytest.mark.asyncio
async def test_song_beacon_lifecycle_post_and_delete():
    channel = FakeChannel(channel_id=10)
    bot = FakeBot(channel)

    client = IPCClient(bot=bot)

    guild_id = 1
    client.update_last_command_channel(guild_id, channel.id)

    song = {
        "title": "Test Song",
        "webpage_url": "https://youtu.be/test"
    }

    # Post the start-of-song beacon
    await client._post_start_of_song_message(guild_id, song)

    # Verify a message was sent
    assert len(channel.messages) == 1
    msg = channel.messages[0]
    assert msg.embed is not None
    assert "Test Song" in (msg.embed.title or "")

    # Ensure internal tracking set
    assert guild_id in client.song_message_by_guild

    # Delete the start-of-song beacon
    await client._delete_start_of_song_message(guild_id)

    # Tracking cleared and message marked deleted
    assert guild_id not in client.song_message_by_guild
    assert msg.deleted is True


