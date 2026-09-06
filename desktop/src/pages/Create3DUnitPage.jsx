import { useNavigate } from 'react-router-dom';
import { NothingYet } from '../data/useCadastre';

/**
 * Creating a unit by hand is not built.
 *
 * What stood here was a four-step wizard that wrote nothing: no import of the API
 * client, no call, no unit. It prefilled a building and a parcel from one demo ward,
 * multiplied a height difference by a magic 55.73 to state a "Calculated Volume",
 * drew a fixed SVG box as a preview of the operator's geometry, and finished by
 * presenting an invented ULPIN with a Draft badge and the line "This unit requires
 * review and approval before it becomes an official record" — for a record that did
 * not exist and never would. An operator who walked those four steps had every reason
 * to believe a unit was waiting in the review queue.
 *
 * The sidecar has no route for it either, and the missing piece is geometry: a unit
 * needs a footprint, and this app has no way to draw one. Until it does, the two paths
 * that genuinely mint units are the ones to point at.
 */
export default function Create3DUnitPage() {
  const navigate = useNavigate();

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Create 3D Property Unit</h1>
          <p className="page-subtitle">
            Defining a vertical property unit by hand, from a footprint drawn on the map
            and a base and top height typed against the project's datum.
          </p>
        </div>
      </div>

      <NothingYet title="Not built yet">
        There is no route on the sidecar for creating a unit by hand, and nothing on this
        screen would write one. What it needs first is a way to draw a footprint: a unit
        is a prism over a real outline, and typing two heights against no geometry
        describes nothing. Until that exists, a form here could only mint an identifier
        for a shape nobody has drawn.
      </NothingYet>

      <div className="card" style={{ marginTop: 20 }}>
        <div className="card-header">
          <div className="card-title">Where units do come from</div>
        </div>
        <div className="card-body" style={{ fontSize: 'var(--text-sm)', lineHeight: 1.7 }}>
          <p style={{ marginBottom: 12 }}>
            <strong>Upload Data</strong> — add a parcel layer or building footprints and
            the project imports them as units, each one carrying the accuracy of the file
            it came from. Add a DEM and a DSM, then run height derivation, and those
            buildings gain a base, a top and a floor stack.
          </p>
          <p style={{ marginBottom: 16 }}>
            <strong>AI Tools</strong> — detection proposes buildings from the project's
            rasters. Nothing it finds becomes a unit until a person accepts it and the
            accepted suggestions are applied, and the decision is recorded with a name
            against it.
          </p>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn btn-primary btn-sm" onClick={() => navigate('/upload')}>
              Upload Data
            </button>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/ai-tools')}>
              AI Tools
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
