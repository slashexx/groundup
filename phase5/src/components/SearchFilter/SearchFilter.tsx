import React, { useCallback } from 'react';
import type { SearchFilterProps } from '../../types/viewer';
import {
  ALL_TYPES,
  ALL_STATUSES,
  STATUS_COLORS,
  toggleItem,
  filterUnits,
} from '../../utils/viewerUtils';

export const SearchFilter: React.FC<SearchFilterProps> = ({
  units,
  filter,
  onFilterChange,
  onSelect,
}) => {
  const queryValue = filter.query ?? '';
  const activeTypes = filter.types ?? ALL_TYPES;
  const activeStatuses = filter.statuses ?? ALL_STATUSES;

  const handleSearchEnter = useCallback(() => {
    const matches = filterUnits(units, filter);
    if (matches.length > 0) {
      onSelect(matches[0].properties.ulpin);
    } else {
      onSelect(null);
    }
  }, [units, filter, onSelect]);

  return (
    <div className="p5-searchfilter">
      <input
        className="p5-search"
        type="search"
        placeholder="Search ULPIN… (Enter selects first match)"
        value={queryValue}
        onChange={(e) => {
          onFilterChange({ ...filter, query: e.target.value });
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            handleSearchEnter();
          }
        }}
      />
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
      <div className="p5-chips" role="group" aria-label="Statuses">
        {ALL_STATUSES.map((status) => {
          const isOn = activeStatuses.includes(status);
          return (
            <button
              key={status}
              type="button"
              className={`p5-chip ${isOn ? 'on' : ''}`}
              style={isOn ? { borderColor: STATUS_COLORS[status], color: STATUS_COLORS[status] } : undefined}
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
  );
};

export default SearchFilter;
