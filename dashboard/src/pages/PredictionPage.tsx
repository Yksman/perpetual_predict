import { motion } from 'framer-motion';
import { DirectionDonut } from '../components/charts/DirectionDonut';
import { AccuracyTimeline } from '../components/charts/AccuracyTimeline';
import { ConfidenceScatter } from '../components/charts/ConfidenceScatter';
import { PredictionTable } from '../components/tables/PredictionTable';
import { useIsMobile } from '../hooks/useMediaQuery';
import type { Prediction, MetricsData } from '../types';

interface PredictionPageProps {
  predictions: Prediction[];
  metrics: MetricsData;
}

export function PredictionPage({ predictions, metrics }: PredictionPageProps) {
  const isMobile = useIsMobile();

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div style={{
        display: 'grid',
        gridTemplateColumns: isMobile ? '1fr' : 'minmax(0, 1fr) minmax(0, 2fr)',
        gap: 'var(--gap)',
        background: 'var(--border)',
      }}>
        <DirectionDonut accuracy={metrics.prediction_accuracy} />
        <AccuracyTimeline predictions={predictions} />
      </div>
      <div style={{
        marginTop: 'var(--gap)',
        background: 'var(--border)',
      }}>
        <ConfidenceScatter predictions={predictions} />
      </div>
      <div style={{ marginTop: 'var(--gap)' }}>
        <PredictionTable predictions={predictions} />
      </div>
    </motion.div>
  );
}
