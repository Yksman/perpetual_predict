import { useState } from 'react';
import { motion } from 'framer-motion';
import { ExperimentSelector } from '../components/experiment/ExperimentSelector';
import { ExperimentSummary } from '../components/experiment/ExperimentSummary';
import { ExperimentEquityCurve } from '../components/experiment/ExperimentEquityCurve';
import { ExperimentComparison } from '../components/experiment/ExperimentComparison';
import { ExperimentStats } from '../components/experiment/ExperimentStats';
import { ExperimentPredictionPairs } from '../components/experiment/ExperimentPredictionPairs';
import type { Experiment } from '../types';

interface ExperimentPageProps {
  experiments: Experiment[];
}

export function ExperimentPage({ experiments }: ExperimentPageProps) {
  const [selectedId, setSelectedId] = useState(experiments[0]?.experiment_id ?? '');
  const selected = experiments.find(e => e.experiment_id === selectedId) ?? experiments[0];

  if (!selected) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      {experiments.length > 1 && (
        <ExperimentSelector
          experiments={experiments}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
      )}
      <ExperimentSummary experiment={selected} />
      <div style={{ marginTop: 'var(--gap)' }}>
        <ExperimentEquityCurve experiment={selected} />
      </div>
      <div style={{ marginTop: 'var(--gap)' }}>
        <ExperimentComparison experiment={selected} />
      </div>
      <div style={{ marginTop: 'var(--gap)' }}>
        <ExperimentStats experiment={selected} />
      </div>
      <div style={{ marginTop: 'var(--gap)' }}>
        <ExperimentPredictionPairs pairs={selected.prediction_pairs} />
      </div>
    </motion.div>
  );
}
