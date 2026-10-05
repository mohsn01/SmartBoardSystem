"""Tuning constants for the call-on-board selection and scoring logic.

Kept in one place so the formula can be quoted and adjusted without hunting
through views.py. See selection/views.py for how each constant is used.
"""

# --- Fairness (who gets called) ---
# A student not called in this many days (or more) gets the full fairness
# boost; a student called today gets none.
RECENCY_WINDOW_DAYS = 7

# An open retry (the student got a question wrong and hasn't fixed it yet)
# multiplies their ticket weight by this much in a LATER class, never the
# same class where they got it wrong.
RETRY_BOOST_MULTIPLIER = 2.0

# --- Points (section 2.4) ---
# Awarded per board call outcome. Going forward only: existing historical
# rows are not retroactively rewritten when this rule changed.
POINTS_SOLVED = 1
POINTS_PARTIAL = 0
POINTS_NOT_SOLVED = -1

# When a student resolves an open retry correctly, the original wrong
# attempt's -1 is refunded (set back to 0) on top of the +1 for the retry
# itself. Set False to keep the original -1 on the books.
RETRY_REFUND = True

# --- Board bonus (section 3.1) ---
# effective_score = mark.average + board_bonus, used for priority/weight so
# a student's board performance can move them from Weak towards Average
# without touching their official Mark.
BOARD_BONUS_PER_RESOLVED_RETRY = 5
BOARD_BONUS_PER_CORRECT_FIRST_TRY = 2
BOARD_BONUS_PER_OPEN_RETRY = -2
BOARD_BONUS_MAX = 15
BOARD_BONUS_MIN = -10
