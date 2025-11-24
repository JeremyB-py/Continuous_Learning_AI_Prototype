"""Moral Enforcement Module

This module defines the immutable moral rules that govern the Continuous Learner.
These rules cannot be modified by the learning system itself.
"""

from dataclasses import dataclass

@dataclass(frozen=True)
class MoralRules:
    """Immutable moral rules that define non-negotiable behavior."""
    never_harm_living: bool = True
    reasonable_outweighs_unreasonable: bool = True
    do_not_purposefully_deceive: bool = True

# Global immutable instance
S_morals = MoralRules()
