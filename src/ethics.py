"""Moral Enforcement Module"""

from dataclasses import dataclass

@dataclass(frozen=True)
class MoralRules:
    never_harm_living: bool = True
    reasonable_outweighs_unreasonable: bool = True
    do_not_purposefully_deceive: bool = True
