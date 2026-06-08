import { useState } from 'react';
import { X, Phone, User, ClipboardCheck, BookOpen, ArrowUpCircle, StickyNote } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ClinicalActionType } from '@/lib/api/types/sense-loop';

interface ActionModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (action: { action_type: ClinicalActionType; notes: string }) => Promise<void>;
  patientName?: string;
  isSaving?: boolean;
}

const categoryOptions: { value: ClinicalActionType; label: string; icon: React.ElementType }[] = [
  { value: 'phone', label: 'Phone Call', icon: Phone },
  { value: 'in-person', label: 'In-Person Visit', icon: User },
  { value: 'order', label: 'Order Placed', icon: ClipboardCheck },
  { value: 'education', label: 'Education Provided', icon: BookOpen },
  { value: 'escalation', label: 'Escalation', icon: ArrowUpCircle },
  { value: 'note', label: 'Clinical Note', icon: StickyNote },
];

export function ActionModal({ isOpen, onClose, onSave, patientName, isSaving = false }: ActionModalProps) {
  const [category, setCategory] = useState<ClinicalActionType>('note');
  const [text, setText] = useState('');

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!text.trim()) return;

    await onSave({
      action_type: category,
      notes: text.trim(),
    });
    setText('');
    setCategory('note');
  };

  const handleClose = () => {
    if (!isSaving) {
      setText('');
      setCategory('note');
      onClose();
    }
  };

  return (
    <div className="sl-modal-overlay" onClick={handleClose}>
      <div className="sl-modal" onClick={(e) => e.stopPropagation()}>
        <div className="sl-modal-header">
          <h3 className="sl-modal-title">
            Log Clinical Action
            {patientName && <span className="text-[var(--sl-text-muted)]"> - {patientName}</span>}
          </h3>
          <button onClick={handleClose} className="sl-btn sl-btn-ghost p-1" disabled={isSaving}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="sl-modal-body">
          {/* Category Selection */}
          <div className="sl-form-group">
            <label className="sl-form-label">Action Type</label>
            <div className="sl-category-grid">
              {categoryOptions.map((option) => {
                const Icon = option.icon;
                return (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setCategory(option.value)}
                    className={cn(
                      'sl-category-option',
                      category === option.value && 'active'
                    )}
                  >
                    <Icon className="w-5 h-5" />
                    <span>{option.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Action Text */}
          <div className="sl-form-group">
            <label className="sl-form-label">Description</label>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Describe the clinical action taken..."
              className="sl-form-textarea"
              rows={4}
              disabled={isSaving}
            />
          </div>
        </div>

        <div className="sl-modal-footer">
          <button
            onClick={handleClose}
            className="sl-btn sl-btn-ghost"
            disabled={isSaving}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="sl-btn sl-btn-primary"
            disabled={!text.trim() || isSaving}
          >
            {isSaving ? 'Saving...' : 'Save Action'}
          </button>
        </div>
      </div>
    </div>
  );
}
