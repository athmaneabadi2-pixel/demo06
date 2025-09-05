import json, os

class Memory:
    def __init__(self, profile_path: str = "profile.json"):
        self.profile_path = profile_path if os.path.exists(profile_path) else None

    def get_profile(self) -> dict:
        if self.profile_path and os.path.exists(self.profile_path):
            with open(self.profile_path, "r", encoding="utf-8") as f:
                return json.load(f)
        # profil par défaut minimal
        return {
            "user": {"display_name": "ami"},
            "preferences": {"tone": "simple", "short_sentences": True}
        }
