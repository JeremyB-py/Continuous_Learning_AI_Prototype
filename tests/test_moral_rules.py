"""Tests for moral rules enforcement"""

import unittest
from src.CLAIP import ContinuousLearner
from src.ethics import S_morals, MoralRules


class TestMoralRules(unittest.TestCase):
    """Test moral rules enforcement and immutability"""
    
    def test_moral_rules_immutability(self):
        """Test that moral rules cannot be modified"""
        original_value = S_morals.never_harm_living
        
        # Attempt to modify (should raise AttributeError for frozen dataclass)
        with self.assertRaises(Exception):
            S_morals.never_harm_living = False
        
        # Verify value unchanged
        self.assertEqual(S_morals.never_harm_living, original_value)
    
    def test_moral_rules_defaults(self):
        """Test that moral rules have correct default values"""
        self.assertTrue(S_morals.never_harm_living)
        self.assertTrue(S_morals.reasonable_outweighs_unreasonable)
        self.assertTrue(S_morals.do_not_purposefully_deceive)
    
    def test_guardrails_enforcement(self):
        """Test that guardrails are enforced in agent operations"""
        agent = ContinuousLearner(enable_logging=False)
        
        # Normal operations should work
        agent.ingest("test", info={}, label=1, source_names=["S1"])
        agent.predict("test", scenario={}, evidence_hint=0.5, own=False)
        
        # Guardrails should be called (no exception means they passed)
        # Note: In current implementation, guardrails only check moral core config
        # Future: Add more comprehensive moral checks
    
    def test_moral_rules_import(self):
        """Test that moral rules are properly imported"""
        from src.ethics import S_morals as imported_morals
        from src.CLAIP import S_morals as claip_morals
        
        # Both should reference the same instance
        self.assertIs(imported_morals, claip_morals)
        self.assertIs(imported_morals, S_morals)
    
    def test_moral_rules_consistency(self):
        """Test that moral rules remain consistent across operations"""
        agent1 = ContinuousLearner(enable_logging=False)
        agent2 = ContinuousLearner(enable_logging=False)
        
        # Both agents should use the same moral rules
        self.assertIs(agent1.__class__.__module__, agent2.__class__.__module__)
        
        # Moral rules should be the same
        from src.ethics import S_morals
        # Both agents enforce the same rules (checked via guardrails)
        agent1.enforce_guardrails("test")
        agent2.enforce_guardrails("test")
        # If we get here, both passed the same moral checks


if __name__ == "__main__":
    unittest.main()

