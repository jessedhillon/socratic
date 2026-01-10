import React from 'react';
import type {
  TranscriptSegmentResponse,
  EvidenceMappingResponse,
} from '../api';

interface TranscriptViewerProps {
  segments: TranscriptSegmentResponse[];
  evidenceMappings?: EvidenceMappingResponse[];
  highlightedCriterion?: string;
}

/**
 * Transcript viewer with evidence highlighting.
 */
const TranscriptViewer: React.FC<TranscriptViewerProps> = ({
  segments,
  evidenceMappings = [],
  highlightedCriterion,
}) => {
  // Build a map of segment_id to evidence info
  const segmentEvidence = React.useMemo(() => {
    const map: Record<
      string,
      { criterion_name: string; strength: string; criterion_id: string }[]
    > = {};

    for (const mapping of evidenceMappings) {
      for (const segmentId of mapping.segment_ids) {
        if (!map[segmentId]) {
          map[segmentId] = [];
        }
        map[segmentId].push({
          criterion_id: mapping.criterion_id,
          criterion_name: mapping.criterion_name || 'Unknown',
          strength: mapping.strength || 'none',
        });
      }
    }

    return map;
  }, [evidenceMappings]);

  return (
    <div className="space-y-4">
      {segments.map((segment) => {
        const isInterviewer = segment.utterance_type === 'interviewer';
        const evidence = segmentEvidence[segment.segment_id] || [];
        const isHighlighted =
          highlightedCriterion &&
          evidence.some((e) => e.criterion_id === highlightedCriterion);

        return (
          <div
            key={segment.segment_id}
            className={`flex ${isInterviewer ? 'justify-start' : 'justify-end'}`}
          >
            <div
              className={`max-w-[80%] rounded-lg p-3 ${
                isInterviewer
                  ? 'bg-gray-100 text-gray-800'
                  : `bg-blue-500 text-white ${
                      isHighlighted ? 'ring-2 ring-yellow-400' : ''
                    }`
              }`}
            >
              <div className="text-xs opacity-70 mb-1">
                {isInterviewer ? 'Interviewer' : 'Learner'}
                {segment.prompt_index != null &&
                  ` (Prompt ${segment.prompt_index + 1})`}
              </div>
              <p className="whitespace-pre-wrap">{segment.content}</p>

              {/* Evidence badges for learner responses */}
              {!isInterviewer && evidence.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {evidence.map((e, idx) => (
                    <span
                      key={`${e.criterion_id}-${idx}`}
                      className={`px-2 py-0.5 rounded text-xs ${
                        e.criterion_id === highlightedCriterion
                          ? 'bg-yellow-300 text-yellow-900'
                          : 'bg-white/20 text-white'
                      }`}
                    >
                      {e.criterion_name} ({e.strength})
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default TranscriptViewer;
