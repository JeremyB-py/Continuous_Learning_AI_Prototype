"""Tests for checkpoint and rollback functionality"""

import unittest
import tempfile
import shutil
from pathlib import Path
from src.CLAIP import ContinuousLearner
from src.checkpoint import create_checkpoint, restore_checkpoint, verify_checkpoint, list_checkpoints


class TestCheckpoints(unittest.TestCase):
    """Test checkpoint creation, verification, and restoration"""
    
    def setUp(self):
        """Set up test environment with temporary checkpoint directory"""
        self.temp_dir = Path(tempfile.mkdtemp())
        # Temporarily override checkpoint directory
        import src.checkpoint as cp_module
        self.original_dir = cp_module.CHECKPOINT_DIR
        cp_module.CHECKPOINT_DIR = self.temp_dir
        
    def tearDown(self):
        """Clean up temporary directory"""
        import src.checkpoint as cp_module
        cp_module.CHECKPOINT_DIR = self.original_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_checkpoint_creation(self):
        """Test that checkpoints are created successfully"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=True)
        agent.ingest("test.subject", info={"val": 1}, label=1, source_names=["Source1"])
        agent.ingest("test.subject", info={"val": 2}, label=0, source_names=["Source2"])
        
        # Create checkpoint (suppress print output)
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            ckpt_path = create_checkpoint(agent, label="test_checkpoint")
        finally:
            sys.stdout = old_stdout
        
        # Verify checkpoint file exists
        self.assertTrue(ckpt_path.exists())
        
        # Verify metadata file exists
        meta_path = ckpt_path.with_suffix(".json")
        self.assertTrue(meta_path.exists())
    
    def test_checkpoint_verification(self):
        """Test checkpoint integrity verification"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=True)
        agent.ingest("test.subject", info={"val": 1}, label=1, source_names=["Source1"])
        
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            ckpt_path = create_checkpoint(agent, label="verify_test")
        finally:
            sys.stdout = old_stdout
        
        # Verify checkpoint (suppress print output)
        sys.stdout = StringIO()
        try:
            result = verify_checkpoint(ckpt_path)
        finally:
            sys.stdout = old_stdout
        self.assertTrue(result)
    
    def test_checkpoint_restore(self):
        """Test restoring agent state from checkpoint"""
        # Create agent and add some state
        agent1 = ContinuousLearner(enable_logging=False, enable_checkpoints=True)
        agent1.ingest("test.subject", info={"val": 1}, label=1, source_names=["Source1"])
        agent1.ingest("test.subject", info={"val": 2}, label=0, source_names=["Source2"])
        original_event_count = agent1.event_count
        original_reward = agent1.total_reward
        
        # Create checkpoint (suppress print output)
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            ckpt_path = create_checkpoint(agent1, label="restore_test")
        finally:
            sys.stdout = old_stdout
        
        # Create new agent and restore (suppress print output)
        sys.stdout = StringIO()
        try:
            agent2 = restore_checkpoint(str(ckpt_path))
        finally:
            sys.stdout = old_stdout
        
        # Verify state is restored
        self.assertEqual(agent2.event_count, original_event_count)
        self.assertEqual(agent2.total_reward, original_reward)
        self.assertEqual(len(agent2.kb.claims), 2)
        self.assertEqual(len(agent2.sources.sources), 2)
    
    def test_checkpoint_state_preservation(self):
        """Test that all critical state is preserved in checkpoint"""
        agent1 = ContinuousLearner(enable_logging=False, enable_checkpoints=True)
        
        # Add diverse state
        agent1.ingest("subject1", info={}, label=1, source_names=["S1", "S2"])
        agent1.ingest("subject2", info={}, label=0, source_names=["S3"])
        agent1.predict("subject1", scenario={}, evidence_hint=0.7, own=False)
        
        # Store some values
        original_progress = {k: v.seen_items for k, v in agent1.progress.items()}
        original_gk_prior = agent1.gk.prior("subject1")
        original_replay_size = len(agent1.replay)
        
        # Checkpoint and restore (suppress print output)
        import sys
        from io import StringIO
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            ckpt_path = create_checkpoint(agent1, label="state_test")
            agent2 = restore_checkpoint(str(ckpt_path))
        finally:
            sys.stdout = old_stdout
        
        # Verify all state preserved
        self.assertEqual(agent2.event_count, agent1.event_count)
        for subject, items in original_progress.items():
            self.assertEqual(agent2.progress[subject].seen_items, items)
        self.assertAlmostEqual(agent2.gk.prior("subject1"), original_gk_prior, places=3)
        self.assertEqual(len(agent2.replay), original_replay_size)
    
    def test_checkpoint_automatic_creation(self):
        """Test automatic checkpoint creation during learning"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=True)
        
        # Run enough events to trigger checkpoint (every 50 events)
        for i in range(55):
            agent.ingest(f"subject_{i%3}", info={}, label=i%2, source_names=[f"S{i%2}"])
        
        # Check that checkpoint was created
        checkpoints = list(self.temp_dir.glob("core_state_*.pkl"))
        self.assertGreater(len(checkpoints), 0, "At least one checkpoint should be created")


if __name__ == "__main__":
    unittest.main()

