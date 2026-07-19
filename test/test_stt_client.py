"""Tests for STTClient factory dispatch and the canonical session contract."""

import pytest

from steely.stt import STTClient, STTConfig, STTEvent, EventType
from steely.stt.base import STTProvider
from steely.stt.languages import to_provider_language
from steely.stt.providers.fake import FakeProvider, FakeSession


def test_unknown_provider_raises():
    with pytest.raises(ValueError):
        STTClient("carrier-pigeon")


def test_dispatch_is_case_insensitive():
    assert STTClient("FAKE").provider_name == "fake"


def test_instance_passthrough():
    provider = FakeProvider()
    client = STTClient(provider)
    assert client.provider is provider


def test_bad_provider_type_raises():
    with pytest.raises(TypeError):
        STTClient(123)


def test_validate_delegates():
    assert STTClient(FakeProvider()).validate() is True


@pytest.mark.asyncio
async def test_stream_yields_canonical_events_in_order():
    client = STTClient("fake")
    session = await client.open_session(STTConfig(language="pt-BR"))
    out = [ev async for ev in session]
    assert [e.type for e in out] == [EventType.INTERIM, EventType.INTERIM, EventType.FINAL]
    assert out[-1].is_final
    assert out[-1].text == "olá mundo"
    assert out[-1].language == "pt-BR"
    # timestamps are integer milliseconds
    assert all(isinstance(e.start, int) and isinstance(e.end, int) for e in out)


@pytest.mark.asyncio
async def test_push_end_close_lifecycle():
    session = await STTClient("fake").open_session(STTConfig())
    await session.push_frame(b"\x00\x01" * 160)
    await session.end_input()
    async with session:
        _ = [ev async for ev in session]
    assert isinstance(session, FakeSession)
    assert session.ended is True
    assert session.closed is True
    assert len(session.pushed) == 1


@pytest.mark.asyncio
async def test_custom_script_is_emitted():
    script = [STTEvent(EventType.FINAL, "tudo bem", 100, 500, language="pt-BR")]
    client = STTClient(FakeProvider(script=script))
    session = await client.open_session(STTConfig())
    out = [ev async for ev in session]
    assert len(out) == 1 and out[0].text == "tudo bem" and out[0].start == 100


def test_language_normalization_per_provider():
    # worker speaks "pt-BR"; each adapter maps to its own code
    assert to_provider_language("assemblyai", "pt-BR") == "pt"
    assert to_provider_language("deepgram", "pt-BR") == "pt-BR"
    assert to_provider_language("google", "pt-BR") == "pt-BR"
    # unmapped tag falls through unchanged
    assert to_provider_language("deepgram", "fr-FR") == "fr-FR"


def test_all_real_providers_are_stt_providers():
    # importing the providers package is safe without any SDK installed
    from steely.stt import providers

    for cls in (
        providers.DeepgramProvider,
        providers.AssemblyAIProvider,
        providers.GoogleProvider,
        providers.AzureProvider,
        providers.AmazonTranscribeProvider,
    ):
        assert issubclass(cls, STTProvider)
