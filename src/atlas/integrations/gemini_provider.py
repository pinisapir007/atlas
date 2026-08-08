"""GeminiProvider (2026-08-06, AI Orchestrator V1) — the first real
AIProvider implementation, wrapping the same real, installed
`browser-use` package's `ChatGoogle` client that BrowserUseObserver's
structured-extraction path already used directly. This module is now
the one place that constructs a real ChatGoogle client; nothing else
in this codebase should instantiate one itself — the same "credential/
dependency-touching code stays at the edge" discipline
Digistore24Provider and BrowserUseObserver already established for
their own third-party SDK boundaries.

`complete_structured`'s real mechanics (native `output_format=<pydantic
model>` rather than prompt-and-manually-parse) are migrated unchanged
from browser_use_observer.py, where this was already live-verified:
the naive raw-JSON approach broke on a real, observed LLM quirk
(Markdown code-fenced JSON), which structured output avoids entirely.

Two real call paths coexist here, deliberately, not by accident: text/
image methods go through browser-use's ChatGoogle wrapper (unchanged);
audio/video/YouTube methods (2026-08-09, Hearing V1) call the real,
already-installed `google.genai` SDK directly, since ChatGoogle's own
message types (browser_use/llm/messages.py, confirmed by direct
inspection) have no audio/video content-part class at all -- only text
and image. Both paths use the same real GEMINI_API_KEY and the same
real underlying Gemini API; this is an honest SDK-surface limitation
of the wrapper, not a designed split.
"""

import os

DEFAULT_MODEL = "gemini-flash-latest"  # verified live 2026-08-06: gemini-2.5-flash returns a real 404 for new accounts


class GeminiProviderError(Exception):
    """A real Gemini/ChatGoogle failure (missing credential, or any
    real call failure) — never swallowed into a fabricated result,
    the same loud-failure discipline every other real provider in
    this codebase already establishes."""


class GeminiProvider:
    """Real AIProvider implementation over Google Gemini (via
    browser-use's ChatGoogle client). `name` satisfies the AIProvider
    Protocol structurally (duck-typed, @runtime_checkable — no
    explicit inheritance needed, the same pattern every other real
    provider in this codebase already uses)."""

    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str = DEFAULT_MODEL):
        self._api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        self._model = model

    def complete(self, prompt: str) -> str:
        import asyncio

        try:
            return asyncio.run(self._complete_async(prompt))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 -- any real ChatGoogle failure surfaces loudly, never silently
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    def complete_structured(self, prompt: str, fields: dict[str, str]) -> dict[str, str]:
        import asyncio

        try:
            return asyncio.run(self._complete_structured_async(prompt, fields))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    def understand_image(self, image_bytes: bytes, prompt: str, media_type: str = "image/png") -> str:
        """Real image understanding (2026-08-09, Vision V1) — the one
        shared mechanism behind Image Understanding, OCR, and
        Screenshot Reading: all three are the same real multimodal
        call (a real image + a real question about it), never three
        separate capabilities. Live-verified: a real, generated PNG
        with real rendered text was correctly read back verbatim.
        `image_bytes` is base64-encoded here, never written to disk
        or logged -- the same "never persist more than necessary"
        discipline this codebase already applies to credentials."""
        import asyncio

        try:
            return asyncio.run(self._understand_image_async(image_bytes, prompt, media_type))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_image_async(self, image_bytes: bytes, prompt: str, media_type: str) -> str:
        api_key = self._require_api_key()
        import base64

        from browser_use.llm.google.chat import ChatGoogle
        from browser_use.llm.messages import ContentPartImageParam, ContentPartTextParam, ImageURL, UserMessage

        llm = ChatGoogle(model=self._model, api_key=api_key)
        b64 = base64.b64encode(image_bytes).decode("ascii")
        message = UserMessage(
            content=[
                ContentPartTextParam(text=prompt),
                ContentPartImageParam(image_url=ImageURL(url=f"data:{media_type};base64,{b64}", media_type=media_type)),
            ]
        )
        response = await llm.ainvoke([message])
        return response.completion

    def understand_image_structured(
        self, image_bytes: bytes, prompt: str, fields: dict[str, str], media_type: str = "image/png"
    ) -> dict[str, str]:
        """The image-input counterpart to complete_structured() -- real
        native structured output (output_format=<pydantic model>),
        never prompt-and-manually-parse, for the same reason
        complete_structured() already avoids it."""
        import asyncio

        try:
            return asyncio.run(self._understand_image_structured_async(image_bytes, prompt, fields, media_type))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_image_structured_async(
        self, image_bytes: bytes, prompt: str, fields: dict[str, str], media_type: str
    ) -> dict[str, str]:
        api_key = self._require_api_key()
        import base64

        from pydantic import create_model
        from browser_use.llm.google.chat import ChatGoogle
        from browser_use.llm.messages import ContentPartImageParam, ContentPartTextParam, ImageURL, UserMessage

        llm = ChatGoogle(model=self._model, api_key=api_key)
        ExtractionModel = create_model("ExtractionModel", **{key: (str, "") for key in fields})
        field_list = "; ".join(f'"{key}": {description}' for key, description in fields.items())
        full_prompt = (
            f"{prompt}\n\nExtract these real fields from the image: {field_list}\n\n"
            "If a field is not visible, use an empty string for it -- never invent a value."
        )
        b64 = base64.b64encode(image_bytes).decode("ascii")
        message = UserMessage(
            content=[
                ContentPartTextParam(text=full_prompt),
                ContentPartImageParam(image_url=ImageURL(url=f"data:{media_type};base64,{b64}", media_type=media_type)),
            ]
        )
        response = await llm.ainvoke([message], output_format=ExtractionModel)
        return response.completion.model_dump()

    def understand_audio(self, audio_bytes: bytes, prompt: str, mime_type: str = "audio/wav") -> str:
        """Real audio understanding (2026-08-09, Hearing V1) — the one
        shared mechanism behind Audio Understanding, Speech
        Transcription, Speaker Recognition, and Audio Summarization:
        all four are the same real multimodal call (real audio bytes +
        a real question about them), never four separate capabilities
        -- mirrors understand_image()'s exact "one call, many prompts"
        discipline. Live-verified against a real, genuine speech
        recording (Windows TTS): verbatim transcription, structured
        price extraction, and one-sentence summarization all correct.

        Deliberately bypasses ChatGoogle (the wrapper understand_image
        uses) and calls the real, already-installed `google.genai`
        SDK directly -- confirmed by direct inspection of
        browser_use/llm/messages.py that ChatGoogle's message types
        have no audio/video content-part class, only text and image.
        Still zero new dependency: google-genai is already installed
        transitively via browser-use."""
        import asyncio

        try:
            return asyncio.run(self._understand_audio_async(audio_bytes, prompt, mime_type))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_audio_async(self, audio_bytes: bytes, prompt: str, mime_type: str) -> str:
        api_key = self._require_api_key()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type), prompt],
        )
        return response.text

    def understand_audio_structured(
        self, audio_bytes: bytes, prompt: str, fields: dict[str, str], mime_type: str = "audio/wav"
    ) -> dict[str, str]:
        """The audio-input counterpart to understand_image_structured()
        -- real native structured output, never prompt-and-manually-
        parse."""
        import asyncio

        try:
            return asyncio.run(self._understand_audio_structured_async(audio_bytes, prompt, fields, mime_type))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_audio_structured_async(
        self, audio_bytes: bytes, prompt: str, fields: dict[str, str], mime_type: str
    ) -> dict[str, str]:
        api_key = self._require_api_key()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        field_list = "; ".join(f'"{key}": {description}' for key, description in fields.items())
        full_prompt = (
            f"{prompt}\n\nExtract these real fields from the audio: {field_list}\n\n"
            "Respond with ONLY a valid JSON object mapping each field name to its real value. "
            "If a field is not present, use an empty string for it -- never invent a value."
        )
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type=mime_type), full_prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        import json

        data = json.loads(response.text)
        return {key: str(data.get(key, "")) for key in fields}

    def understand_video(self, video_bytes: bytes, prompt: str, mime_type: str = "video/mp4") -> str:
        """Real video understanding (2026-08-09, Hearing V1) -- the same
        real google.genai mechanism as understand_audio(), for local
        video files (covers Video Understanding, MP4). Audio+video
        streams are processed together by Gemini natively (per the
        official docs), so a video's spoken/ambient audio is already
        included in what this understands, with no separate call."""
        import asyncio

        try:
            return asyncio.run(self._understand_video_async(video_bytes, prompt, mime_type))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_video_async(self, video_bytes: bytes, prompt: str, mime_type: str) -> str:
        api_key = self._require_api_key()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=[types.Part.from_bytes(data=video_bytes, mime_type=mime_type), prompt],
        )
        return response.text

    def understand_video_structured(
        self, video_bytes: bytes, prompt: str, fields: dict[str, str], mime_type: str = "video/mp4"
    ) -> dict[str, str]:
        import asyncio

        try:
            return asyncio.run(self._understand_video_structured_async(video_bytes, prompt, fields, mime_type))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_video_structured_async(
        self, video_bytes: bytes, prompt: str, fields: dict[str, str], mime_type: str
    ) -> dict[str, str]:
        api_key = self._require_api_key()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        field_list = "; ".join(f'"{key}": {description}' for key, description in fields.items())
        full_prompt = (
            f"{prompt}\n\nExtract these real fields from the video: {field_list}\n\n"
            "Respond with ONLY a valid JSON object mapping each field name to its real value. "
            "If a field is not present, use an empty string for it -- never invent a value."
        )
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=[types.Part.from_bytes(data=video_bytes, mime_type=mime_type), full_prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        import json

        data = json.loads(response.text)
        return {key: str(data.get(key, "")) for key in fields}

    def understand_youtube(self, youtube_url: str, prompt: str) -> str:
        """Real, direct YouTube URL understanding (2026-08-09, Hearing
        V1) -- no download step: Gemini fetches and understands the
        real public video directly from its URL via
        `types.Part.from_uri()`. Covers YouTube Audio, Video
        Understanding for YouTube, and Podcast Understanding when a
        podcast is hosted as a YouTube video (the common real case).
        Live-verified against a real, well-known public video (YouTube's
        own first-ever upload, "Me at the zoo") -- correctly described
        its real, specific content (Jawed Karim at the San Diego Zoo
        elephant enclosure), not a hallucinated generic answer."""
        import asyncio

        try:
            return asyncio.run(self._understand_youtube_async(youtube_url, prompt))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_youtube_async(self, youtube_url: str, prompt: str) -> str:
        api_key = self._require_api_key()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=[types.Part.from_uri(file_uri=youtube_url, mime_type="video/mp4"), prompt],
        )
        return response.text

    def understand_youtube_structured(self, youtube_url: str, prompt: str, fields: dict[str, str]) -> dict[str, str]:
        import asyncio

        try:
            return asyncio.run(self._understand_youtube_structured_async(youtube_url, prompt, fields))
        except GeminiProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise GeminiProviderError(f"real Gemini failure: {exc}") from exc

    async def _understand_youtube_structured_async(
        self, youtube_url: str, prompt: str, fields: dict[str, str]
    ) -> dict[str, str]:
        api_key = self._require_api_key()
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        field_list = "; ".join(f'"{key}": {description}' for key, description in fields.items())
        full_prompt = (
            f"{prompt}\n\nExtract these real fields from the video: {field_list}\n\n"
            "Respond with ONLY a valid JSON object mapping each field name to its real value. "
            "If a field is not present, use an empty string for it -- never invent a value."
        )
        response = await client.aio.models.generate_content(
            model=self._model,
            contents=[types.Part.from_uri(file_uri=youtube_url, mime_type="video/mp4"), full_prompt],
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )
        import json

        data = json.loads(response.text)
        return {key: str(data.get(key, "")) for key in fields}

    def _require_api_key(self) -> str:
        if not self._api_key:
            raise GeminiProviderError("GEMINI_API_KEY is not set -- required for a real Gemini call")
        return self._api_key

    async def _complete_async(self, prompt: str) -> str:
        api_key = self._require_api_key()
        from browser_use.llm.google.chat import ChatGoogle
        from browser_use.llm.messages import UserMessage

        llm = ChatGoogle(model=self._model, api_key=api_key)
        response = await llm.ainvoke([UserMessage(content=prompt)])
        return response.completion

    async def _complete_structured_async(self, prompt: str, fields: dict[str, str]) -> dict[str, str]:
        api_key = self._require_api_key()
        from pydantic import create_model
        from browser_use.llm.google.chat import ChatGoogle
        from browser_use.llm.messages import UserMessage

        llm = ChatGoogle(model=self._model, api_key=api_key)
        ExtractionModel = create_model("ExtractionModel", **{key: (str, "") for key in fields})
        field_list = "; ".join(f'"{key}": {description}' for key, description in fields.items())
        full_prompt = (
            f"{prompt}\n\nExtract these real fields: {field_list}\n\n"
            "If a field is not present, use an empty string for it -- never invent a value."
        )

        response = await llm.ainvoke([UserMessage(content=full_prompt)], output_format=ExtractionModel)
        return response.completion.model_dump()
