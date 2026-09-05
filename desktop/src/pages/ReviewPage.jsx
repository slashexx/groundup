import { useEffect, useMemo, useState } from 'react';
import { Icons } from '../components/Icons';
import { cadastre, reviewRows } from '../data/cadastreApi';
import { DataSourceBanner, NothingYet, useCadastreDocument } from '../data/useCadastre';

const stateFlow = ['Draft', 'Processing', 'Needs Review', 'Approved', 'Replaced', 'Closed'];

/** How many of the queue this screen will draw at once.
 *
 *  The Trivandrum pilot arrives with about six thousand units in `needs_review`, and one
 *  row per unit is thirty thousand DOM nodes that make the page unusable to scroll. The
 *  count in the header is the real one; this only bounds what is painted, and the list
 *  says so at the bottom rather than ending as though the queue did. */
const VISIBLE = 200;

/** A live unit, in the shape this screen already renders. */
function toRecord(r) {
  return {
    id: r.id,
    ulpin: r.ulpin,
    provisional: r.provisional,
    type: r.type,
    building: r.floor === null ? '—' : `Floor index ${r.floor}`,
    floor: r.floor ?? '—',
    submittedBy: r.createdBy,
    submittedDate: r.recordedFrom ? new Date(r.recordedFrom).toLocaleString() : '—',
    aiConfidence: r.confidence === null || r.confidence === undefined
      ? 'n/a'
      : `${(r.confidence * 100).toFixed(1)}%`,
    errors: r.errors,
    warnings: r.warnings,
    unacknowledged: r.unacknowledged,
    approvable: r.approvable,
    validationState: r.validationState,
    status: 'Needs Review',
    state: 'review',
  };
}

export default function ReviewPage() {
  const { doc, live, status: loadStatus, error: loadError, reload } = useCadastreDocument();
  const [selectedId, setSelectedId] = useState(null);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState(null);
  // What the last transition actually did. Kept at page level because a unit leaves the
  // queue the moment it is approved: rendering the outcome inside its own row would make
  // the record vanish on click with nothing said about where it went.
  const [outcome, setOutcome] = useState(null);

  const records = useMemo(
    () => (live && doc ? reviewRows(doc).map(toRecord) : []),
    [live, doc],
  );

  useEffect(() => {
    if (!records.some(r => r.id === selectedId)) setSelectedId(records[0]?.id ?? null);
  }, [records, selectedId]);

  const selected = records.find(r => r.id === selectedId);

  // The state machine is the authority. Approval is guarded on a recorded validation run
  // with zero errors and every warning acknowledged, and freezes the ULPIN. A refusal is
  // shown verbatim rather than being reflected in the UI as success — the guard is the
  // feature, and a screen that reports an approval the register did not record is the one
  // failure this app must never have.
  const handleAction = async (action) => {
    setActionError(null);
    setOutcome(null);
    const target = action === 'approve' ? 'approved' : 'draft';
    setBusy(true);
    try {
      const res = await cadastre.transition(selectedId, target, 'reviewer', comment || null);
      setComment('');
      setOutcome({
        unitId: res.unit_id,
        status: res.status,
        ulpin: res.ulpin,
        sentBack: action !== 'approve',
      });
      await reload();
    } catch (e) {
      setActionError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="review-page" style={{ position: 'relative' }}>
      {/* Review List */}
      <div className="review-list">
        <div className="panel-header">
          <span className="panel-title">Review Queue ({records.length})</span>
        </div>
        <DataSourceBanner status={loadStatus} error={loadError} onRetry={reload} />
        <div className="review-list-items">
          {records.slice(0, VISIBLE).map(record => (
            <div key={record.id}
              className={`review-item${selectedId === record.id ? ' active' : ''}`}
              onClick={() => setSelectedId(record.id)}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--accent-primary)', fontWeight: 600 }}>
                  {record.ulpin}
                </span>
                <span className="status-badge review" style={{ fontSize: '9px' }}>
                  {record.status}
                </span>
              </div>
              <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-secondary)' }}>
                {record.type} · {record.building}
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted)', marginTop: 2 }}>
                Submitted by {record.submittedBy} · {record.submittedDate}
              </div>
              {(record.errors > 0 || record.warnings > 0) && (
                <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                  {record.errors > 0 && <span style={{ fontSize: '10px', color: 'var(--status-error)' }}>⚠ {record.errors} error</span>}
                  {record.warnings > 0 && <span style={{ fontSize: '10px', color: 'var(--status-warning)' }}>⚡ {record.warnings} warning</span>}
                </div>
              )}
            </div>
          ))}
          {records.length > VISIBLE && (
            <div style={{ padding: 12, fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Showing the first {VISIBLE} of {records.length}. The rest are in the queue,
              not missing — narrow it on the Search screen to reach a particular unit.
            </div>
          )}
        </div>
      </div>

      {/* Review Detail */}
      <div className="review-detail">
        {outcome && (
          <div style={{
            padding: 16, marginBottom: 24, borderRadius: 'var(--radius-md)',
            background: outcome.sentBack ? 'var(--bg-tertiary)' : 'var(--status-success-bg)',
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <Icons.Check style={{ width: 20, height: 20, color: outcome.sentBack ? 'var(--text-tertiary)' : 'var(--status-success)' }} />
            <span style={{ color: outcome.sentBack ? 'var(--text-secondary)' : 'var(--status-success)', fontWeight: 600, fontSize: 'var(--text-sm)' }}>
              {outcome.sentBack
                ? `${outcome.unitId} sent back to draft. It has left the review queue.`
                : `${outcome.unitId} approved. ULPIN ${outcome.ulpin} is now frozen to it.`}
            </span>
          </div>
        )}

        {!selected && live && (
          <NothingYet title="Nothing waiting for review">
            No unit in this project is in <code>needs_review</code>. Units arrive here after
            ingest or after a suggestion is applied; a queue of zero is the register saying
            there is nothing to decide, not that it has not looked.
          </NothingYet>
        )}

        {selected && (
          <>
          <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
            Review Record
          </h2>

          {/* State Flow */}
          <div className="review-flow">
            {stateFlow.map((state, i) => {
              const currentIdx = stateFlow.indexOf('Needs Review');
              const isDone = i < currentIdx;
              const isCurrent = state === 'Needs Review';
              return (
                <div key={state} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className={`review-flow-step ${isCurrent ? 'current' : isDone ? 'done' : ''}`}>
                    {state}
                  </span>
                  {i < stateFlow.length - 1 && <span className="review-flow-arrow">→</span>}
                </div>
              );
            })}
          </div>

          {/* Details Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
            <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
              <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
                Property Details
              </h3>
              <div className="property-field">
                <span className="property-field-label">ULPIN</span>
                <span className="property-field-value" style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent-primary)' }}>
                  {selected.ulpin}
                  {selected.provisional && (
                    <span style={{ marginLeft: 6, fontFamily: 'var(--font-family)', color: 'var(--text-muted)', fontSize: '10px' }}>
                      provisional · assigned at approval
                    </span>
                  )}
                </span>
              </div>
              <div className="property-field"><span className="property-field-label">Type</span><span className="property-field-value">{selected.type}</span></div>
              <div className="property-field"><span className="property-field-label">Building</span><span className="property-field-value">{selected.building}</span></div>
              <div className="property-field"><span className="property-field-label">Floor</span><span className="property-field-value">{selected.floor}</span></div>
              <div className="property-field"><span className="property-field-label">Submitted By</span><span className="property-field-value">{selected.submittedBy}</span></div>
              <div className="property-field"><span className="property-field-label">Date</span><span className="property-field-value">{selected.submittedDate}</span></div>
            </div>

            <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)', borderRadius: 'var(--radius-lg)', padding: 20 }}>
              <h3 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 12 }}>
                Quality Assessment
              </h3>
              <div className="property-field">
                <span className="property-field-label">AI Confidence</span>
                <span className="property-field-value" style={{ color: parseFloat(selected.aiConfidence) > 90 ? 'var(--status-success)' : 'var(--status-warning)' }}>
                  {selected.aiConfidence}
                </span>
              </div>
              <div className="property-field">
                <span className="property-field-label">Errors</span>
                <span className="property-field-value" style={{ color: selected.errors > 0 ? 'var(--status-error)' : 'var(--status-success)' }}>
                  {selected.errors}
                </span>
              </div>
              <div className="property-field">
                <span className="property-field-label">Warnings</span>
                <span className="property-field-value" style={{ color: selected.warnings > 0 ? 'var(--status-warning)' : 'var(--status-success)' }}>
                  {selected.warnings}
                </span>
              </div>
              {Number.isFinite(parseFloat(selected.aiConfidence)) ? (
                <div style={{ marginTop: 12 }}>
                  <div className="ai-confidence-bar" style={{ height: 6 }}>
                    <div className={`ai-confidence-fill ${parseFloat(selected.aiConfidence) > 90 ? 'high' : 'medium'}`}
                      style={{ width: selected.aiConfidence }} />
                  </div>
                </div>
              ) : (
                // Not an AI-originated unit. An empty bar would read as zero confidence.
                <div style={{ marginTop: 12, fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                  Not AI-derived — no confidence score applies.
                </div>
              )}
            </div>
          </div>

          {/* Comment */}
          <div style={{ marginBottom: 24 }}>
            <label className="form-label" style={{ marginBottom: 8, display: 'block' }}>Review Comment</label>
            <textarea
              style={{
                width: '100%', height: 80, background: 'var(--bg-input)', border: '1px solid var(--border-primary)',
                borderRadius: 'var(--radius-md)', padding: '8px 12px', color: 'var(--text-primary)',
                fontSize: 'var(--text-sm)', fontFamily: 'var(--font-family)', resize: 'vertical', outline: 'none'
              }}
              placeholder="Add review comments..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          {/* Actions */}
          {actionError && (
            <div style={{
              padding: 12, marginBottom: 12, borderRadius: 'var(--radius-md)',
              background: 'var(--status-error-bg)', color: 'var(--status-error)',
              fontSize: 'var(--text-sm)',
            }}>
              {actionError}
            </div>
          )}
          {selected.approvable === false && (
            <div style={{
              padding: 12, marginBottom: 12, borderRadius: 'var(--radius-md)',
              background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)',
              fontSize: 'var(--text-sm)',
            }}>
              {selected.errors > 0
                ? `${selected.errors} error(s) must be fixed and the checks re-run before this can be approved.`
                : `${selected.unacknowledged} warning(s) must be acknowledged on the Check Errors screen first.`}
            </div>
          )}
          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn btn-success btn-lg" disabled={busy}
              onClick={() => handleAction('approve')}
              title={selected.approvable ? 'Approve and freeze the ULPIN' : 'Blocked by the validation guard'}>
              <Icons.Check style={{ width: 16, height: 16 }} /> {busy ? 'Working…' : 'Approve'}
            </button>
            {/* There is no rejected status. FR-09's machine takes needs_review to approved
                or back to draft and nowhere else, so a Reject button could only be Send
                Back wearing a word the register would never record. */}
            <button className="btn btn-danger btn-lg" disabled
              title="The record lifecycle has no rejected state — needs_review goes to approved or back to draft. Use Send Back for Correction.">
              <Icons.Close style={{ width: 16, height: 16 }} /> Reject
            </button>
            <button className="btn btn-secondary btn-lg" disabled={busy} onClick={() => handleAction('sendback')}
              title="Return this unit to draft for correction">
              <Icons.ArrowLeft style={{ width: 16, height: 16 }} /> Send Back for Correction
            </button>
          </div>
          </>
        )}
      </div>
    </div>
  );
}
