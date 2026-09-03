import { useState } from 'react'
import type { UnitFilter, UnitType, ValidationState, ViewerUnit } from './types'
import { TYPE_LABELS, UNIT_TYPES, VALIDATION_LABELS, VALIDATION_STATES } from './types'
import { VALIDATION_COLORS } from './theme'
import { applyFilter } from './filter'

interface SearchFilterProps {
  units: ViewerUnit[]
  filter: UnitFilter
  onFilterChange: (filter: UnitFilter) => void
  onSelect: (unitId: string | null) => void
}

function toggle<T>(all: T[], active: T[] | undefined, value: T): T[] {
  const current = new Set(active ?? all)
  if (current.has(value)) current.delete(value)
  else current.add(value)
  return [...current]
}

export function SearchFilter({ units, filter, onFilterChange, onSelect }: SearchFilterProps) {
  const [query, setQuery] = useState(filter.query ?? '')
  const activeTypes = filter.types ?? UNIT_TYPES
  const activeValidation = filter.validation ?? VALIDATION_STATES

  const submit = () => {
    const match = applyFilter(units, { ...filter, query })[0]
    onSelect(match ? match.unit_id : null)
  }

  return (
    <div className="p5-searchfilter">
      <input
        className="p5-search"
        type="search"
        placeholder="search ULPIN / unit id"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          onFilterChange({ ...filter, query: e.target.value })
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') submit()
        }}
      />
      <div className="p5-chips" role="group" aria-label="Unit types">
        {UNIT_TYPES.map((t: UnitType) => (
          <button
            key={t}
            type="button"
            className={`p5-chip ${activeTypes.includes(t) ? 'on' : ''}`}
            onClick={() => onFilterChange({ ...filter, types: toggle(UNIT_TYPES, filter.types, t) })}
          >
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>
      <div className="p5-chips" role="group" aria-label="Validation states">
        {VALIDATION_STATES.map((v: ValidationState) => (
          <button
            key={v}
            type="button"
            className={`p5-chip ${activeValidation.includes(v) ? 'on' : ''}`}
            style={
              activeValidation.includes(v)
                ? { borderColor: VALIDATION_COLORS[v], color: VALIDATION_COLORS[v] }
                : undefined
            }
            onClick={() =>
              onFilterChange({
                ...filter,
                validation: toggle(VALIDATION_STATES, filter.validation, v),
              })
            }
          >
            {VALIDATION_LABELS[v]}
          </button>
        ))}
      </div>
    </div>
  )
}
