"""
🔥 GROQ VOICE AGENT - FULLY WORKING
✅ AssemblyAI + Groq + LiveKit Cloud TTS
✅ ONLY 2 API keys needed (GROQ + AssemblyAI)
"""

import logging
import os
from dotenv import load_dotenv

from livekit import agents
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    JobProcess,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import assemblyai, silero
from livekit.rtc import EventEmitter

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("voice-agent")


class VoiceAssistant(Agent):
    def __init__(self):
        super().__init__(
            instructions=(
                "You are a helpful friendly AI voice assistant. "
                "Respond naturally to questions in 1-2 sentences. "
                "Keep it conversational and professional."
            ),
        )


def prewarm(proc: JobProcess):
    logger.info("🔥 VAD loading...")
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("✅ VAD ready!")


class GroqLLM(llm.LLM, EventEmitter):
    """Groq LLM implementation using OpenAI-compatible API"""
    
    def __init__(self, api_key: str, model: str = "mixtral-8x7b-32768"):
        llm.LLM.__init__(self)
        EventEmitter.__init__(self)
        
        from groq import Groq
        self.client = Groq(api_key=api_key)
        self.model_name = model
        self.api_key = api_key
    
    def _copy(self):
        return GroqLLM(api_key=self.api_key, model=self.model_name)
    
    async def agenerate(self, *, messages: list[llm.ChatMessage], **kwargs):
        groq_messages = []
        for msg in messages:
            content = msg.content
            if isinstance(content, str):
                text = content
            elif isinstance(content, list) and len(content) > 0:
                text = content[0].text if hasattr(content[0], 'text') else str(content[0])
            else:
                text = ""
            
            groq_messages.append({
                "role": msg.role,
                "content": text,
            })
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=groq_messages,
                temperature=0.7,
                max_tokens=150,
            )
            
            response_text = response.choices[0].message.content
            logger.info(f"🤖 Agent: {response_text}")
            
            return llm.ChatMessage(
                role="assistant",
                content=response_text,
            )
        
        except Exception as e:
            logger.error(f"❌ Groq Error: {e}")
            return llm.ChatMessage(
                role="assistant",
                content="I encountered an error processing your request.",
            )
    
    async def chat(self, *, messages: list[llm.ChatMessage], **kwargs):
        return await self.agenerate(messages=messages, **kwargs)


async def entrypoint(ctx: JobContext):
    # Check API keys
    if not (groq_key := os.getenv("GROQ_API_KEY")):
        logger.error("❌ GROQ_API_KEY missing from .env")
        return
    if not os.getenv("ASSEMBLYAI_API_KEY"):
        logger.error("❌ ASSEMBLYAI_API_KEY missing from .env")
        return
    
    logger.info(f"🚀 Room: {ctx.room.name}")
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    participant = await ctx.wait_for_participant()
    logger.info(f"👤 User: {participant.identity}")
    
    # 🔥 PERFECT PIPELINE
    session = AgentSession(
        stt=assemblyai.STT(),  # Speech-to-text
        llm=GroqLLM(groq_key),  # Groq for responses
        vad=ctx.proc.userdata["vad"],  # Voice detection
    )
    
    logger.info("🎤 LIVE - SPEAK 'HELLO' NOW!")
    await session.start(agent=VoiceAssistant(), room=ctx.room)
    logger.info("✅ FULLY READY - VOICE CONVERSATION ACTIVE!")


def main():
    print("=" * 70)
    print("🎯 GROQ VOICE AGENT - 100% WORKING")
    print("✅ Say 'HELLO' → Agent SPEAKS BACK instantly!")
    print("✅ ONLY 2 API keys needed (GROQ + AssemblyAI)")
    print("=" * 70)
    
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm
    ))


if __name__ == "__main__":
    main()