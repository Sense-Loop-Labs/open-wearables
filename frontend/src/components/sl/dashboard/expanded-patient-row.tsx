import {
  Wind,
  Footprints,
  Moon,
  MessageCircle,
  AlertTriangle,
  ClipboardList,
  Plus,
  GraduationCap,
  ArrowUpCircle,
  AlertOctagon,
  Phone,
  User,
  ClipboardCheck,
  BookOpen,
  StickyNote,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { AlertBadge } from './alert-badge';

export interface QuestionnaireConcern {
  questionText: string;
  answerText: string;
  severity: 'warning' | 'critical';
  reportedAt: string;
}

export interface ClinicalAction {
  id: string;
  category: 'phone' | 'in-person' | 'order' | 'education' | 'escalation' | 'note';
  categoryDisplay: string;
  text: string;
  occurredAt: string;
  performerName?: string;
  isMarkdown?: boolean;
}

export type ActionCategory = ClinicalAction['category'];

export interface ExpandedPatientDetails {
  surgeryType: string | null;
  respiratoryRate: number | null;
  activityMinutesToday: number | null;
  sleepDurationHours: number | null;
  questionnaireConcerns: QuestionnaireConcern[];
  actionLog: ClinicalAction[];
}

interface ExpandedPatientRowProps {
  patientId: string;
  details: ExpandedPatientDetails | null;
  loading: boolean;
  vitalAlertCodes: string[];
  hasCriticalAlert: boolean;
  onProvideEducation: (patientId: string) => void;
  onEscalateToPA: (patientId: string) => void;
  onAdviseED: (patientId: string) => void;
  onOpenActionModal: (patientId: string) => void;
}

const categoryIcons: Record<string, React.ElementType> = {
  phone: Phone,
  'in-person': User,
  order: ClipboardCheck,
  education: BookOpen,
  escalation: ArrowUpCircle,
  note: StickyNote,
};

function formatRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  return `${diffDays}d ago`;
}

export function ExpandedPatientRow({
  patientId,
  details,
  loading,
  vitalAlertCodes,
  hasCriticalAlert,
  onProvideEducation,
  onEscalateToPA,
  onAdviseED,
  onOpenActionModal,
}: ExpandedPatientRowProps) {
  if (loading) {
    return (
      <div className="sl-expanded-row">
        <div className="sl-expanded-loading">
          <div className="sl-spinner" />
          <span>Loading patient details...</span>
        </div>
      </div>
    );
  }

  if (!details) {
    return (
      <div className="sl-expanded-row">
        <div className="sl-expanded-error">
          <AlertTriangle className="w-5 h-5" />
          <span>Failed to load patient details</span>
        </div>
      </div>
    );
  }

  return (
    <div className="sl-expanded-row">
      <div className="sl-expanded-content">
        {/* Left column - Additional vitals & info */}
        <div className="sl-expanded-section">
          <h4 className="sl-expanded-section-title">Additional Information</h4>
          <div className="sl-expanded-info-grid">
            <div className="sl-expanded-info-item">
              <span className="label">Surgery Type</span>
              <span className="value">{details.surgeryType || 'Not specified'}</span>
            </div>
            <div className="sl-expanded-info-item">
              <Wind className="icon" />
              <span className="label">Resp. Rate</span>
              <span className="value">
                {details.respiratoryRate !== null ? `${details.respiratoryRate} bpm` : '--'}
              </span>
            </div>
            <div className="sl-expanded-info-item">
              <Footprints className="icon" />
              <span className="label">Activity</span>
              <span className="value">
                {details.activityMinutesToday !== null ? `${details.activityMinutesToday} min` : '--'}
              </span>
            </div>
            <div className="sl-expanded-info-item">
              <Moon className="icon" />
              <span className="label">Sleep</span>
              <span className="value">
                {details.sleepDurationHours !== null ? `${details.sleepDurationHours.toFixed(1)} hrs` : '--'}
              </span>
            </div>
          </div>
        </div>

        {/* Middle column - Alerts & Concerns */}
        <div className="sl-expanded-section">
          <h4 className="sl-expanded-section-title">
            <AlertTriangle className="w-4 h-4" />
            Active Alerts
          </h4>
          {vitalAlertCodes.length === 0 && details.questionnaireConcerns.length === 0 ? (
            <p className="sl-expanded-empty">No active alerts or concerns</p>
          ) : (
            <div className="space-y-2">
              {vitalAlertCodes.map((code, idx) => (
                <AlertBadge
                  key={idx}
                  code={code}
                  severity={code.includes('critical') ? 'critical' : 'warning'}
                />
              ))}
              {details.questionnaireConcerns.map((concern, idx) => (
                <div key={idx} className="sl-questionnaire-concern">
                  <div className="flex items-start gap-2">
                    <MessageCircle className={cn(
                      'w-4 h-4 mt-0.5',
                      concern.severity === 'critical' ? 'text-red-500' : 'text-yellow-500'
                    )} />
                    <div>
                      <p className="text-sm font-medium">{concern.questionText}</p>
                      <p className="text-sm text-[var(--sl-text-muted)]">{concern.answerText}</p>
                      <p className="text-xs text-[var(--sl-text-subtle)]">
                        {formatRelativeTime(concern.reportedAt)}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right column - Quick Actions & Log */}
        <div className="sl-expanded-section">
          <h4 className="sl-expanded-section-title">
            <ClipboardList className="w-4 h-4" />
            Quick Actions
          </h4>
          <div className="sl-quick-actions">
            <button
              onClick={() => onProvideEducation(patientId)}
              className="sl-btn sl-btn-secondary"
            >
              <GraduationCap className="w-4 h-4" />
              Provide Education
            </button>
            <button
              onClick={() => onEscalateToPA(patientId)}
              className="sl-btn sl-btn-secondary"
            >
              <ArrowUpCircle className="w-4 h-4" />
              Escalate to PA
            </button>
            {hasCriticalAlert && (
              <button
                onClick={() => onAdviseED(patientId)}
                className="sl-btn sl-btn-danger"
              >
                <AlertOctagon className="w-4 h-4" />
                Advise ED
              </button>
            )}
            <button
              onClick={() => onOpenActionModal(patientId)}
              className="sl-btn sl-btn-primary"
            >
              <Plus className="w-4 h-4" />
              Log Action
            </button>
          </div>

          {details.actionLog.length > 0 && (
            <div className="sl-action-log">
              <h5 className="sl-action-log-title">Recent Actions</h5>
              {details.actionLog.slice(0, 3).map((action) => {
                const Icon = categoryIcons[action.category] || StickyNote;
                return (
                  <div key={action.id} className="sl-action-log-item">
                    <Icon className="w-4 h-4 text-[var(--sl-text-muted)]" />
                    <div className="flex-1">
                      <p className="text-sm">{action.text}</p>
                      <p className="text-xs text-[var(--sl-text-muted)]">
                        {action.performerName && `${action.performerName} - `}
                        {formatRelativeTime(action.occurredAt)}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
