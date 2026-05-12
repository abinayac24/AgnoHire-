class VoiceHandler:
    def build_greeting(self, candidate_name: str, topic: str) -> str:
        return (
            f"Hello {candidate_name}. Welcome to your AI voice interview. "
            f"We will begin with questions about {topic}. Please answer clearly and confidently."
        )

    def normalize_transcript(self, transcript: str) -> str:
        normalized = " ".join((transcript or "").strip().split())
        return normalized or "No answer captured."


voice_handler = VoiceHandler()
