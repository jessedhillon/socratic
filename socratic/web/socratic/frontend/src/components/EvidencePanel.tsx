import React from 'react';
import type { EvidenceMappingResponse, AssessmentFlag } from '../api';

interface EvidencePanelProps {
  evidenceMappings: EvidenceMappingResponse[];
  strengths: string[];
  gaps: string[];
  reasoningSummary: string | null;
  flags: AssessmentFlag[];
  onCriterionHover?: (criterionId: string | null) => void;
  highlightedCriterion?: string;
}

const strengthBadgeColors: Record<string, string> = {
  strong: 'bg-green-100 text-green-800 border-green-300',
  moderate: 'bg-blue-100 text-blue-800 border-blue-300',
  weak: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  none: 'bg-gray-100 text-gray-600 border-gray-300',
};

const flagDescriptions: Record<AssessmentFlag, string> = {
  high_fluency_low_substance:
    'The learner spoke fluently but provided limited substantive evidence of understanding.',
  repeated_evasion:
    'The learner repeatedly avoided directly answering questions.',
  vocabulary_mirroring:
    'The learner used terminology from questions without demonstrating comprehension.',
  inconsistent_reasoning:
    'The learner made contradictory statements during the assessment.',
  possible_gaming:
    'Patterns suggest the learner may have been trying to game the assessment.',
  low_confidence:
    'The evaluation system has low confidence in this assessment result.',
};

const formatFlagName = (flag: AssessmentFlag): string => {
  return flag
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

/**
 * Panel showing rubric-to-evidence mapping for educator review.
 */
const EvidencePanel: React.FC<EvidencePanelProps> = ({
  evidenceMappings,
  strengths,
  gaps,
  reasoningSummary,
  flags,
  onCriterionHover,
  highlightedCriterion,
}) => {
  return (
    <div className="space-y-6">
      {/* Flags Section */}
      {flags.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="font-semibold text-red-800 mb-2">Review Flags</h3>
          <ul className="space-y-2">
            {flags.map((flag) => (
              <li key={flag} className="text-sm">
                <span className="font-medium text-red-700">
                  {formatFlagName(flag)}:
                </span>{' '}
                <span className="text-red-600">
                  {flagDescriptions[flag] || 'Flag detected'}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Strengths & Gaps */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-green-50 border border-green-200 rounded-lg p-4">
          <h3 className="font-semibold text-green-800 mb-2">Strengths</h3>
          {strengths.length > 0 ? (
            <ul className="space-y-1 text-sm text-green-700">
              {strengths.map((s, idx) => (
                <li key={idx}>+ {s}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-green-600 italic">
              No specific strengths identified
            </p>
          )}
        </div>

        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <h3 className="font-semibold text-orange-800 mb-2">
            Areas for Growth
          </h3>
          {gaps.length > 0 ? (
            <ul className="space-y-1 text-sm text-orange-700">
              {gaps.map((g, idx) => (
                <li key={idx}>- {g}</li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-orange-600 italic">
              No specific gaps identified
            </p>
          )}
        </div>
      </div>

      {/* Rubric Criteria Evidence */}
      <div>
        <h3 className="font-semibold text-gray-800 mb-3">Rubric Evidence</h3>
        <div className="space-y-3">
          {evidenceMappings.map((mapping) => (
            <div
              key={mapping.criterion_id}
              className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                highlightedCriterion === mapping.criterion_id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300'
              }`}
              onMouseEnter={() => onCriterionHover?.(mapping.criterion_id)}
              onMouseLeave={() => onCriterionHover?.(null)}
            >
              <div className="flex justify-between items-start mb-2">
                <h4 className="font-medium text-gray-900">
                  {mapping.criterion_name || 'Unknown Criterion'}
                </h4>
                <span
                  className={`px-2 py-0.5 rounded text-xs border ${
                    strengthBadgeColors[mapping.strength || 'none']
                  }`}
                >
                  {mapping.strength || 'none'}
                </span>
              </div>

              {mapping.evidence_summary ? (
                <p className="text-sm text-gray-600 mb-2">
                  "{mapping.evidence_summary}"
                </p>
              ) : (
                <p className="text-sm text-gray-400 italic mb-2">
                  No evidence extracted
                </p>
              )}

              {mapping.failure_modes_detected.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {mapping.failure_modes_detected.map((fm) => (
                    <span
                      key={fm}
                      className="px-2 py-0.5 rounded text-xs bg-red-100 text-red-700"
                    >
                      {fm}
                    </span>
                  ))}
                </div>
              )}

              <p className="text-xs text-gray-400 mt-2">
                {mapping.segment_ids.length} transcript segment(s) linked
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Reasoning Summary */}
      {reasoningSummary && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
          <h3 className="font-semibold text-gray-800 mb-2">AI Reasoning</h3>
          <p className="text-sm text-gray-600">{reasoningSummary}</p>
        </div>
      )}
    </div>
  );
};

export default EvidencePanel;
