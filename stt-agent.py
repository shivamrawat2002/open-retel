"""🔥 GROQ VOICE AGENT - FINAL STABLE (PRODUCTION READY)"""

import logging
import os
from dotenv import load_dotenv
from contextlib import asynccontextmanager

from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
    TurnHandlingOptions,
)
from livekit.plugins import assemblyai, silero, elevenlabs
from livekit.rtc import EventEmitter


# ------------------ INIT ------------------
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")


# ------------------ PREWARM ------------------
def prewarm(proc: JobProcess):
    logger.info("🔥 Loading VAD...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("✅ VAD ready!")


# ------------------ GROQ LLM ------------------
class GroqLLM(llm.LLM, EventEmitter):
    def __init__(self, api_key: str):
        super().__init__()
        EventEmitter.__init__(self)

        from groq import Groq
        self.client = Groq(api_key=api_key)

    async def agenerate(self, *, messages, **kwargs):
        try:
            if not messages:
                # LiveKit side: content must be list[str]
                messages = [
                    llm.ChatMessage(
                        role="user",
                        content=["Hello"]
                    )
                ]

            groq_messages = []

            for msg in messages:
                if not msg:
                    continue

                content = msg.content

                if isinstance(content, list):
                    text = " ".join([str(x) for x in content if x])
                else:
                    text = str(content) if content else ""

                text = text.strip()

                if text:
                    groq_messages.append({
                        "role": msg.role,
                        "content": text  # ← Groq wants plain string
                    })

            if not groq_messages:
                groq_messages = [{"role": "user", "content": "Hello"}]

            logger.info(f"📨 Sending to LLM: {groq_messages}")

            # ✅ Use a currently supported model from Groq dashboard:
            model = "openai/gpt-oss-120b"  # or "mixtral-8x7b-32768"
            response = self.client.chat.completions.create(
                model=model,
                messages=groq_messages,
                temperature=0.7,
                max_tokens=150,
            )

            reply = response.choices[0].message.content

            if not reply or not reply.strip():
                reply = "Hello! How can I help you?"

            reply = reply.strip()

            logger.info(f"🤖 {reply}")

            return reply

        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return "Hello! I'm here to help."

    # ✅ REQUIRED FOR LIVEKIT
    @asynccontextmanager
    async def chat(self, messages=None, **kwargs):
        response = await self.agenerate(messages=messages, **kwargs)

        async def generator():
            yield response

        yield generator()


# ------------------ AGENT ------------------
class VoiceAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a helpful AI voice assistant. "
                "Always respond clearly and conversationally in 1-2 sentences."
            ),
        )


# ------------------ ENTRYPOINT ------------------
async def entrypoint(ctx: JobContext):
    groq_key = os.getenv("GROQ_API_KEY")
    assembly_key = os.getenv("ASSEMBLYAI_API_KEY")
    # ✅ FIX: Check both possible env var names
    eleven_key = os.getenv("ELEVEN_API_KEY") or os.getenv("ELEVENLABS_API_KEY")

    if not groq_key:
        logger.error("❌ Missing GROQ_API_KEY")
        return
    if not assembly_key:
        logger.error("❌ Missing ASSEMBLYAI_API_KEY")
        return
    if not eleven_key:
        logger.error("❌ Missing ELEVEN_API_KEY or ELEVENLABS_API_KEY")
        return

    logger.info(f"🚀 Room: {ctx.room.name}")

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    try:
        participant = await ctx.wait_for_participant()
        logger.info(f"👤 User: {participant.identity}")
    except Exception:
        logger.warning("⚠️ No participant joined")
        return

    # ✅ FULL PIPELINE
    session = AgentSession(
        stt=assemblyai.STT(),
        llm=GroqLLM(groq_key),
        tts=elevenlabs.TTS(
            api_key=eleven_key,
            voice_id="21m00Tcm4TlvDq8ikWAM",  # your ElevenLabs voice ID
            # model_id="eleven_multilingual_v2",  # optional: pin model
        ),
        vad=ctx.proc.userdata["vad"],
        turn_handling=TurnHandlingOptions(
            allow_interruptions=True,
        ),
    )

    agent = VoiceAssistant()

    logger.info("🎤 READY - Speak now!")

    await session.start(agent=agent, room=ctx.room)


# ------------------ MAIN ------------------
def main():
    print("\n🎯 RUNNING VOICE AGENT...\n")

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
        )
    )


if __name__ == "__main__":
    main()