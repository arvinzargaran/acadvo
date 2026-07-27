import { useState, useRef } from 'react';
import { parseSyllabus } from '../../api/degree';
import { getErrorMessage } from '../../utils/errors';

export default function SyllabusUpload({ courseId, onParsed }) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState('');
  const [results, setResults] = useState([]);
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

  async function handleFiles(fileList) {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    setError('');
    setResults([]);
    setIsUploading(true);

    let allAssessments = [];
    const fileResults = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setProgress(`Parsing ${file.name} (${i + 1}/${files.length})...`);
      try {
        const { data } = await parseSyllabus(courseId, file);
        allAssessments = [...allAssessments, ...data];
        fileResults.push({ name: file.name, count: data.length, ok: true });
      } catch (err) {
        const detail = getErrorMessage(err, 'Parse failed');
        fileResults.push({ name: file.name, count: 0, ok: false, error: detail });
      }
    }

    setResults(fileResults);
    setProgress('');
    setIsUploading(false);

    if (allAssessments.length > 0) {
      onParsed(allAssessments);
    } else if (fileResults.every(r => !r.ok)) {
      setError('All files failed to parse. Try different files.');
    }
  }

  function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    handleFiles(e.dataTransfer.files);
  }

  function handleInputChange(e) {
    handleFiles(e.target.files);
    e.target.value = '';
  }

  return (
    <div className="space-y-2">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`relative border-2 border-dashed rounded-xl p-6 text-center transition-all ${
          isDragging
            ? 'border-primary-500 bg-primary-500/10'
            : 'border-dark-600 hover:border-dark-500'
        } ${isUploading ? 'pointer-events-none opacity-60' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp"
          multiple
          onChange={handleInputChange}
          className="hidden"
        />

        {isUploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500" />
            <p className="text-dark-300 text-sm">{progress}</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <svg className="w-8 h-8 text-dark-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <div>
              <p className="text-dark-200 text-sm font-medium">
                Drag & drop documents here
              </p>
              <p className="text-dark-400 text-xs mt-0.5">
                Syllabus, course schedule, exam schedule — PDF or image, up to 10 MB each
              </p>
              <p className="text-dark-500 text-[10px] mt-0.5">
                You can select multiple files at once
              </p>
            </div>
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              className="mt-1 px-4 py-2 bg-primary-600 hover:bg-primary-500 text-white text-sm font-medium rounded-lg transition-colors"
            >
              Choose Files
            </button>
          </div>
        )}
      </div>

      {/* Per-file results */}
      {results.length > 1 && (
        <div className="space-y-1">
          {results.map((r, i) => (
            <div key={i} className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg ${r.ok ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
              {r.ok ? (
                <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
              ) : (
                <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
              )}
              <span className="truncate">{r.name}</span>
              <span className="ml-auto flex-shrink-0">
                {r.ok ? `${r.count} assessment${r.count !== 1 ? 's' : ''}` : r.error}
              </span>
            </div>
          ))}
        </div>
      )}

      {error && <p className="text-red-400 text-sm">{error}</p>}
    </div>
  );
}
