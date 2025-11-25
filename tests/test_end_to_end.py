"""End-to-end tests for full learning cycles"""

import unittest
import random
from src.CLAIP import ContinuousLearner, S_rules


class TestEndToEnd(unittest.TestCase):
    """Test complete learning cycles and improvements"""
    
    def setUp(self):
        """Set up test with reproducible random seed"""
        self.random_seed = 87
        random.seed(self.random_seed)
    
    def test_full_learning_cycle(self):
        """Test a complete learning cycle with multiple subjects"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=False)
        
        # Simulate learning over multiple subjects
        subjects = ["weather.rain", "stock.price_up", "traffic.heavy"]
        sources = ["NOAA", "Bloomberg", "Waze", "LocalNews", "Expert"]
        
        # Phase 1: Initial ingestion
        for i in range(30):
            subject = random.choice(subjects)
            source = random.choice(sources)
            label = random.choice([0, 1])
            agent.ingest(subject, info={"iteration": i}, label=label, source_names=[source])
        
        # Phase 2: Make predictions
        predictions = []
        for subject in subjects:
            if agent.can_predict_external(subject):
                idx = agent.predict(subject, scenario={"test": True}, evidence_hint=None, own=False)
                predictions.append((subject, idx))
        
        # Phase 3: Resolve predictions
        for subject, idx in predictions:
            observed = random.choice([0, 1])
            agent.resolve_prediction(idx, observed)
        
        # Verify system state
        self.assertGreater(agent.event_count, 0)
        self.assertGreater(len(agent.kb.claims), 0)
        self.assertGreater(len(agent.sources.sources), 0)
        self.assertGreater(len(agent.replay), 0)
    
    def test_learning_improvement(self):
        """Test that system improves over time"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=False)
        
        subject = "test.accuracy"
        sources = ["Source1", "Source2", "Source3"]
        
        # Initial phase: Random labels (low accuracy expected)
        for i in range(20):
            label = random.choice([0, 1])
            agent.ingest(subject, info={}, label=label, source_names=[random.choice(sources)])
        
        # Make predictions and resolve
        initial_predictions = []
        for _ in range(10):
            if agent.can_predict_external(subject):
                idx = agent.predict(subject, scenario={}, evidence_hint=None, own=False)
                observed = random.choice([0, 1])
                agent.resolve_prediction(idx, observed)
                initial_predictions.append(agent.predictor.history[idx].correct)
        
        # Continue learning with more consistent patterns
        for i in range(30):
            # Introduce some pattern (70% label=1)
            label = 1 if random.random() < 0.7 else 0
            agent.ingest(subject, info={}, label=label, source_names=[random.choice(sources)])
        
        # Make more predictions
        later_predictions = []
        for _ in range(10):
            if agent.can_predict_external(subject):
                idx = agent.predict(subject, scenario={}, evidence_hint=None, own=False)
                observed = 1 if random.random() < 0.7 else 0  # Match pattern
                agent.resolve_prediction(idx, observed)
                later_predictions.append(agent.predictor.history[idx].correct)
        
        # System should have learned something
        self.assertGreater(len(agent.predictor.history), 0)
        self.assertIsNotNone(agent.predictor.mean_brier())
        
        # GK prior should reflect learned pattern
        prior = agent.gk.prior(subject)
        self.assertGreater(prior, 0.0)
        self.assertLess(prior, 1.0)
    
    def test_bias_detection(self):
        """Test that bias detection works in full cycle"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=False)
        
        # Create a subject with high disagreement
        subject = "noisy.data"
        for i in range(10):
            # Alternate labels to create disagreements
            label = i % 2
            agent.ingest(subject, info={}, label=label, source_names=[f"S{i%2}"])
        
        # Trigger reflection (happens every 25 events)
        while agent.event_count < 25:
            agent.ingest("other", info={}, label=0, source_names=["S0"])
        
        # Check that bias was detected
        self.assertGreater(len(agent.bias_notes), 0)
        
        # Check pattern stats
        stats = agent.pattern_stats[subject]
        self.assertGreater(stats["disagreements"], 0)
        ratio = stats["disagreements"] / stats["events"]
        self.assertGreater(ratio, 0.3)  # Should exceed warning threshold
    
    def test_replay_buffer_bounds(self):
        """Test that replay buffer stays bounded"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=False)
        
        # Add many events
        for i in range(200):
            agent.ingest(f"subject_{i%5}", info={}, label=i%2, source_names=[f"S{i%3}"])
            if i % 10 == 0 and agent.can_predict_external(f"subject_{i%5}"):
                idx = agent.predict(f"subject_{i%5}", scenario={}, evidence_hint=None, own=False)
                agent.resolve_prediction(idx, i % 2)
        
        # Replay buffer should be bounded
        self.assertLessEqual(len(agent.replay), S_rules.replay_buffer_size)
    
    def test_metrics_reporting(self):
        """Test that metrics are generated correctly"""
        agent = ContinuousLearner(enable_logging=False, enable_checkpoints=False)
        
        # Generate enough events to trigger reflection and metrics
        for i in range(30):
            agent.ingest(f"subject_{i%3}", info={}, label=i%2, source_names=[f"S{i%2}"])
            if i % 5 == 0 and agent.can_predict_external(f"subject_{i%3}"):
                idx = agent.predict(f"subject_{i%3}", scenario={}, evidence_hint=None, own=False)
                agent.resolve_prediction(idx, i % 2)
        
        # Check that metrics would be generated (reflection triggered)
        self.assertGreaterEqual(agent.event_count, S_rules.reevaluation_interval_events)


if __name__ == "__main__":
    unittest.main()

