"""ChainForge Enterprise: Multi-Modal Agent Orchestration example.

Usage:
    python examples/enterprise/multimodal_example.py
"""
import asyncio, sys, os, tempfile, base64, struct
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from chainforge.enterprise.multimodal import (
    MultiModalAgent, VisionTool, AudioTool, MultiModalMemory,
)
from chainforge.enterprise.multimodal.memory import InteractionRecord

async def main():
    print("=== Multi-Modal Agent Orchestration ===\n")

    # 1. Create a minimal test image
    def create_minimal_png():
        """Create a valid minimal PNG file."""
        import zlib
        def chunk(chunk_type, data):
            c = chunk_type + data
            crc = struct.pack(">I", zlib.crc32(c) & 0xffffffff)
            return struct.pack(">I", len(data)) + c + crc
        ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
        return (b"\x89PNG\r\n\x1a\n" +
                chunk(b"IHDR", ihdr) +
                chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\xff\x00")) +
                chunk(b"IEND", b""))

    png_data = create_minimal_png()
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.write(png_data); tmp.close()
    print(f"1. Created test image: {tmp.name} ({len(png_data)} bytes)")

    # 2. Vision Tool -- encode images (returns ImageContent Pydantic model)
    vision = VisionTool()
    img_content = vision.process(tmp.name)
    print(f"\n2. VisionTool:")
    print(f"   MIME type: {img_content.mime_type}")
    print(f"   Base64 length: {len(img_content.base64_data)} chars")
    print(f"   SHA256: {img_content.metadata.get('sha256', 'N/A')[:16]}...")

    # 3. Audio Tool -- transcribe audio (mode set at construction)
    audio = AudioTool(mode="stub")
    result = audio.process("meeting.mp3")
    print(f"\n3. AudioTool (stub mode):")
    print(f"   Transcription: {result.transcription[:80]}...")

    # 4. Multi-Modal Memory
    memory = MultiModalMemory(store_text=True, store_images=True, store_audio=True)
    memory.add(InteractionRecord(
        text_content="Analysis of Q3 sales chart",
        image_paths=["chart.png"],
        audio_paths=[],
    ))
    memory.add(InteractionRecord(
        text_content="Meeting notes: discussed AI strategy",
        image_paths=[],
        audio_paths=["meeting.mp3"],
    ))

    print(f"\n4. Multi-Modal Memory:")
    print(f"   Stored: {memory.count()} interactions")

    results = memory.search("sales chart")
    print(f"   Search 'sales chart': {len(results)} results")

    image_results = memory.search("Q3", modality_filter="image")
    print(f"   Search 'Q3' (images only): {len(image_results)} results")

    audio_results = memory.search("meeting", modality_filter="audio")
    print(f"   Search 'meeting' (audio only): {len(audio_results)} results")

    # 5. Multi-Modal Agent overview
    print(f"\n5. Multi-Modal Agent:")
    print(f"   Input format: [str, Image(path), Audio(path), ...]")
    print(f"   Pipeline: text pass-through, image -> base64, audio -> transcription")
    print(f"   Integration: MultiModalAgent.from_llm(your_llm)")

    os.unlink(tmp.name)

if __name__ == "__main__":
    asyncio.run(main())
