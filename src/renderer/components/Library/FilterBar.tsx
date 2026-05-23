import React from 'react';
import { FileTypeFilter, SortBy, SortOrder } from '../../types';

interface FilterBarProps {
  search: string;
  onSearchChange: (v: string) => void;
  fileType: FileTypeFilter;
  onFileTypeChange: (v: FileTypeFilter) => void;
  sortBy: SortBy;
  onSortByChange: (v: SortBy) => void;
  sortOrder: SortOrder;
  onSortOrderChange: (v: SortOrder) => void;
  showFlagged: boolean;
  onShowFlaggedChange: (v: boolean) => void;
  totalCount: number;
  selectedCount: number;
}

const FilterBar: React.FC<FilterBarProps> = ({
  search, onSearchChange,
  fileType, onFileTypeChange,
  sortBy, onSortByChange,
  sortOrder, onSortOrderChange,
  showFlagged, onShowFlaggedChange,
  totalCount, selectedCount,
}) => {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-gray-900 border-b border-gray-800 flex-shrink-0">
      {/* Search */}
      <div className="relative flex-1 max-w-xs">
        <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
        </svg>
        <input
          type="text"
          placeholder="Search photos..."
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          className="input-field pl-9 py-1.5 text-sm"
        />
      </div>

      {/* File type filter */}
      <div className="flex rounded-lg overflow-hidden border border-gray-700">
        {(['ALL', 'RAW', 'JPG'] as FileTypeFilter[]).map((type) => (
          <button
            key={type}
            onClick={() => onFileTypeChange(type)}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              fileType === type
                ? 'bg-blue-600 text-white'
                : 'bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700'
            }`}
          >
            {type}
          </button>
        ))}
      </div>

      {/* Sort */}
      <select
        value={sortBy}
        onChange={(e) => onSortByChange(e.target.value as SortBy)}
        className="select-field py-1.5 text-sm w-auto"
      >
        <option value="date_taken">Date Taken</option>
        <option value="filename">Filename</option>
        <option value="file_size">File Size</option>
        <option value="created_at">Date Added</option>
      </select>

      <button
        onClick={() => onSortOrderChange(sortOrder === 'ASC' ? 'DESC' : 'ASC')}
        className="p-1.5 text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
        title={sortOrder === 'ASC' ? 'Sort Descending' : 'Sort Ascending'}
      >
        {sortOrder === 'ASC' ? (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h6m4 0l4-4m0 0l4 4m-4-4v12" />
          </svg>
        ) : (
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4h13M3 8h9m-9 4h9m5-4v12m0 0l-4-4m4 4l4-4" />
          </svg>
        )}
      </button>

      {/* Flagged filter */}
      <button
        onClick={() => onShowFlaggedChange(!showFlagged)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
          showFlagged ? 'bg-red-700/30 text-red-400 border border-red-700/50' : 'text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700'
        }`}
      >
        <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M3 6a3 3 0 013-3h10a1 1 0 01.8 1.6L14.25 7l2.55 2.4A1 1 0 0116 11H6a1 1 0 00-1 1v3a1 1 0 11-2 0V6z" clipRule="evenodd" />
        </svg>
        Flagged
      </button>

      {/* Count */}
      <div className="ml-auto text-xs text-gray-500">
        {selectedCount > 0 ? (
          <span className="text-blue-400">{selectedCount} selected of {totalCount}</span>
        ) : (
          <span>{totalCount.toLocaleString()} photos</span>
        )}
      </div>
    </div>
  );
};

export default FilterBar;
