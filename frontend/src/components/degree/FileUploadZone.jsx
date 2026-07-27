import { useState, useRef } from 'react';
import { parseDegreeDocument } from '../../api/degree';
import ParsingLoader from './ParsingLoader';
import { getErrorMessage } from '../../utils/errors';

export default function FileUploadZone({ onParsed, accept = '.pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xls,.csv' }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState('');
  const inputRef = useRef(null);

  function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }

  function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }

  async function handleFile(file) {
    if (!file) return;
    setError('');
    setIsParsing(true);
    setFinishing(false);
    try {
      const { data } = await parseDegreeDocument(file);
      // Brief "finishing" state so the bar hits 100% before fade-out
      setFinishing(true);
      await new Promise((r) => setTimeout(r, 600));
      setIsParsing(false);
      setFinishing(false);
      onParsed(data);
    } catch (err) {
      setIsParsing(false);
      setFinishing(false);
      setError(getErrorMessage(err, 'Failed to parse document. Please try a different file.'));
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    handleFile(file);
  }

  function handleInputChange(e) {
    const file = e.target.files[0];
    handleFile(file);
    e.target.value = '';
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all overflow-hidden ${
          isDragging
            ? 'border-primary-500 bg-primary-500/10'
            : 'border-dark-600 hover:border-dark-500'
        } ${isParsing ? 'pointer-events-none min-h-[280px]' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
        />

        {/* AI Parsing Loader overlay */}
        <ParsingLoader visible={isParsing} finishing={finishing} />

        {/* Default upload prompt (hidden behind loader when parsing) */}
        <div className={`flex flex-col items-center gap-3 transition-opacity duration-300 ${isParsing ? 'opacity-0' : 'opacity-100'}`}>
          <svg className="w-10 h-10 text-dark-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
          </svg>
          <div>
            <p className="text-dark-200 text-sm font-medium">
              Drag & drop your degree checklist or academic calendar here
            </p>
            <p className="text-dark-400 text-xs mt-1">
              PDF, PNG, JPEG, Excel, or CSV — up to 10 MB
            </p>
          </div>
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="mt-1 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-lg transition-colors"
          >
            Choose File
          </button>
        </div>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}
    </div>
  );
}
