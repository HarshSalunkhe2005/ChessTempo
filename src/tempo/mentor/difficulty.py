"""Phase 3: dynamic difficulty controller.

Rather than a learned model, this is a simple rating-style controller —
similar in spirit to how Elo itself updates: nudge a "strength" value up or
down after each game based on the outcome and how close it was, instead of
locking the bot to a fixed level chosen once at signup.

The strength value is consumed by move selection (tempo.game.play) as a
knob that blends "play the human-predicted move" against "play the
engine-best move," and/or as a softmax temperature over the model's move
probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DifficultyController:
    """Tracks a single user's current strength estimate.

    `strength` is on a 0.0-1.0 scale:
      - 0.0  -> play the raw human-move-prediction output (weakest, most
               human-like/error-prone)
      - 1.0  -> blend heavily toward engine-best moves (strongest)
    """

    strength: float = 0.3  # starting point; overridden by the user's chosen starting difficulty
    k_factor: float = 0.05  # how big an update per game, like Elo's K
    history: list[float] = field(default_factory=list)

    STARTING_DIFFICULTY_MAP = {
        "beginner": 0.15,
        "casual": 0.30,
        "club": 0.50,
        "strong": 0.70,
    }

    @classmethod
    def from_starting_choice(cls, choice: str) -> "DifficultyController":
        return cls(strength=cls.STARTING_DIFFICULTY_MAP.get(choice, 0.30))

    def update_after_game(self, user_won: bool, was_close: bool) -> None:
        """Nudge strength based on the outcome.

        `was_close` (e.g. decided in the endgame / low eval swing, vs. a
        blowout) softens the update — a narrow loss shouldn't crank
        difficulty down as hard as a rout.
        """
        delta = self.k_factor * (0.5 if was_close else 1.0)
        if user_won:
            self.strength = min(1.0, self.strength + delta)
        else:
            self.strength = max(0.0, self.strength - delta)
        self.history.append(self.strength)

    def update_mid_game(self, user_blunder_rate: float) -> None:
        """Optional finer-grained signal: if the user is blundering a lot
        in the current game, ease off immediately rather than waiting for
        the game to end."""
        if user_blunder_rate > 0.3:
            self.strength = max(0.0, self.strength - self.k_factor * 0.5)
