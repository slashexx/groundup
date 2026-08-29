import React, { useMemo, useState, useCallback } from 'react';
import type { SearchFilterProps } from '../../types/viewer';
import {
  ALL_TYPES,
  ALL_STATUSES,
  STATUS_COLORS,
  toggleItem,
} from '../../utils/viewerUtils';

function searchByUlpin(
  units: SearchFilterProps['units'],
  query: string
) {
  const term = query.trim().toLowerCase();
  if (!term) return [];
  return units.filter((unit) =>
    unit.properties.ulpin.toLowerCase().includes(term)
  );
}

export const SearchFilter: React.FC<SearchFilterProps> = ({
  units,
  filter,
  onFilterChange,
  onSelect,
}) => {
  const [searchText, setSearchText] = useState('');
  const [searchAttempted, setSearchAttempted] = useState(false);

  const activeTypes = filter.types ?? ALL_TYPES;
  const activeStatuses = filter.statuses ?? ALL_STATUSES;

  const matches = useMemo(
    () => searchByUlpin(units, searchText),
    [units, searchText]
  );

  const showNoMatch =
    searchAttempted && searchText.trim().length > 0 && matches.length === 0;

  const handleSearchSelect = useCallback(
    (ulpin: string) => {
      setSearchText(ulpin);
      setSearchAttempted(true);
      onSelect(ulpin);
    },
    [onSelect]
  );

  const handleSearchSubmit = useCallback(() => {
    setSearchAttempted(true);
    if (matches.length > 0) {
      onSelect(matches[0].properties.ulpin);
    }
  }, [matches, onSelect]);

  return (
    <div className="p5-searchfilter">
      <div className="p5-search-wrap">
        <input
          className="p5-search"
          type="search"
          placeholder="Search ULPIN (prefix or partial)…"
          value={searchText}
          onChange={(event) => {
            setSearchText(event.target.value);
            setSearchAttempted(false);
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              handleSearchSubmit();
            }
          }}
          list="ulpin-suggestions"
          autoComplete="off"
        />
        <datalist id="ulpin-suggestions">
          {matches.slice(0, 8).map((unit) => (
            <option key={unit.properties.ulpin} value={unit.properties.ulpin} />
          ))}
        </datalist>
        {showNoMatch && (
          <p className="p5-search-empty" role="status">
            No matching ULPIN
          </p>
        )}
        {searchText.trim().length > 0 && matches.length > 0 && (
          <ul className="p5-search-results" role="listbox">
            {matches.slice(0, 6).map((unit) => (
              <li key={unit.properties.ulpin}>
                <button
                  type="button"
                  className="p5-search-result"
                  onClick={() => handleSearchSelect(unit.properties.ulpin)}
                >
                  {unit.properties.ulpin}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="p5-filter-group">
        <div className="p5-filter-head">
          <span className="p5-filter-label">Type</span>
          <button
            type="button"
            className="p5-filter-all"
            onClick={() => onFilterChange({ ...filter, types: [...ALL_TYPES] })}
          >
            All
          </button>
        </div>
        <div className="p5-chips" role="group" aria-label="Unit types">
          {ALL_TYPES.map((type) => {
            const isOn = activeTypes.includes(type);
            return (
              <button
                key={type}
                type="button"
                className={`p5-chip ${isOn ? 'on' : ''}`}
                onClick={() =>
                  onFilterChange({
                    ...filter,
                    types: toggleItem(ALL_TYPES, filter.types, type),
                  })
                }
              >
                {type}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p5-filter-group">
        <div className="p5-filter-head">
          <span className="p5-filter-label">Status</span>
          <button
            type="button"
            className="p5-filter-all"
            onClick={() =>
              onFilterChange({ ...filter, statuses: [...ALL_STATUSES] })
            }
          >
            All
          </button>
        </div>
        <div className="p5-chips" role="group" aria-label="Statuses">
          {ALL_STATUSES.map((status) => {
            const isOn = activeStatuses.includes(status);
            return (
              <button
                key={status}
                type="button"
                className={`p5-chip ${isOn ? 'on' : ''}`}
                style={
                  isOn
                    ? { borderColor: STATUS_COLORS[status], color: STATUS_COLORS[status] }
                    : undefined
                }
                onClick={() =>
                  onFilterChange({
                    ...filter,
                    statuses: toggleItem(ALL_STATUSES, filter.statuses, status),
                  })
                }
              >
                {status}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default SearchFilter;
