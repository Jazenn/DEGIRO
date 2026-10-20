import React, { useState, useRef } from 'react';
import { X, Upload, FileText, CheckCircle2, AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { parseDegiroCsv, CsvParseResult } from '../utils/csvParser';
import { saveTransactions } from '../services/portfolioData';
import { triggerPriceRefresh } from '../services/priceRefresh';

export interface CsvUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (result: CsvParseResult) => void;
  existingHashes?: string[];
}

export const CsvUploadModal: React.FC<CsvUploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
  existingHashes: _existingHashes,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [parseResult, setParseResult] = useState<CsvParseResult | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [replaceExisting, setReplaceExisting] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const readFileContent = async (file: File): Promise<string> => {
    if (typeof file.text === 'function') {
      return await file.text();
    }
    return new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve((reader.result as string) || '');
      reader.onerror = () => reject(reader.error || new Error('Failed to read file'));
      reader.readAsText(file);
    });
  };

  const handleProcessFile = async (file: File) => {
    setSelectedFile(file);
    setIsParsing(true);
    setErrorMessage(null);
    setParseResult(null);

    try {
      const text = await readFileContent(file);
      const result = parseDegiroCsv(text);

      if (!result.success) {
        setErrorMessage(
          result.errors.length > 0
            ? result.errors.join('. ')
            : 'Unsupported DEGIRO CSV format: file could not be parsed.'
        );
      } else {
        setParseResult(result);
      }
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to read file.');
    } finally {
      setIsParsing(false);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleProcessFile(file);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleProcessFile(file);
    }
  };

  const handleConfirmImport = async () => {
    if (parseResult && parseResult.success) {
      setIsSaving(true);
      try {
        await saveTransactions(parseResult.transactions, undefined, undefined, replaceExisting);
        await triggerPriceRefresh({
          dispatchType: 'repository_dispatch',
          eventType: 'degiro_csv_uploaded',
        });
      } catch (err) {
        console.warn('Failed to save transactions or trigger refresh:', err);
      } finally {
        setIsSaving(false);
        onUploadSuccess(parseResult);
        onClose();
      }
    }
  };

  const resetState = () => {
    setSelectedFile(null);
    setParseResult(null);
    setErrorMessage(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="csv-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm overflow-y-auto"
    >
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col my-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 id="csv-modal-title" className="text-lg font-bold text-white">
                Upload DEGIRO CSV
              </h2>
              <p className="text-xs text-slate-400">
                Dutch &amp; English Account.csv or Transactions.csv
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close modal"
            className="min-h-[44px] min-w-[44px] flex items-center justify-center rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-5 space-y-5">
          {/* File Picker & Drop Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragOver(true);
            }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center gap-3 ${
              isDragOver
                ? 'border-sky-500 bg-sky-500/5'
                : 'border-slate-700 hover:border-slate-600 bg-slate-950/40'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              id="csv-file-input"
              aria-label="Select CSV File"
              accept=".csv,text/csv"
              onChange={handleFileChange}
              className="hidden"
            />

            <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-slate-300">
              {isParsing ? (
                <RefreshCw className="w-6 h-6 animate-spin text-sky-400" />
              ) : selectedFile ? (
                <FileText className="w-6 h-6 text-sky-400" />
              ) : (
                <Upload className="w-6 h-6" />
              )}
            </div>

            <div>
              <span className="text-sm font-semibold text-slate-200 block">
                {selectedFile ? selectedFile.name : 'Choose file or drag & drop'}
              </span>
              <span className="text-xs text-slate-400 mt-1 block">
                Directly from mobile Files/Downloads or desktop
              </span>
            </div>
          </div>

          {/* Error Message */}
          {errorMessage && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Immediate Summary Feedback */}
          {parseResult && parseResult.success && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs font-mono text-slate-400">
                <span className="flex items-center gap-1.5 text-emerald-400">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Validated Successfully
                </span>
                <button
                  type="button"
                  onClick={resetState}
                  className="text-slate-400 hover:text-slate-200 underline"
                >
                  Change file
                </button>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
                  <span className="block text-xs text-slate-400 font-mono">
                    Rows Processed
                  </span>
                  <span className="block text-xl font-bold font-mono text-white mt-1">
                    {parseResult.rowsProcessed}
                  </span>
                </div>
                <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
                  <span className="block text-xs text-slate-400 font-mono">
                    New Transactions
                  </span>
                  <span className="block text-xl font-bold font-mono text-emerald-400 mt-1">
                    {parseResult.newRows}
                  </span>
                </div>
                <div className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 text-center">
                  <span className="block text-xs text-slate-400 font-mono">
                    Duplicates Skipped
                  </span>
                  <span className="block text-xl font-bold font-mono text-amber-400 mt-1">
                    {parseResult.duplicatesSkipped}
                  </span>
                </div>
              </div>

              <label className="flex items-center gap-2.5 text-xs text-slate-300 cursor-pointer select-none bg-slate-950/40 p-3 rounded-xl border border-slate-800 hover:border-slate-700 transition">
                <input
                  type="checkbox"
                  checked={replaceExisting}
                  onChange={(e) => setReplaceExisting(e.target.checked)}
                  className="rounded border-slate-700 bg-slate-900 text-sky-500 focus:ring-sky-500 focus:ring-offset-0 h-4 w-4"
                />
                <span>
                  Clean replace (replaces stored history to clear prior duplicate transactions)
                </span>
              </label>

              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-slate-500" />
                Deduplication verified via canonical transaction business keys.
              </p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 p-5 border-t border-slate-800 bg-slate-950/30">
          <button
            type="button"
            onClick={onClose}
            className="min-h-[44px] px-5 py-2.5 rounded-xl border border-slate-700 bg-slate-800 hover:bg-slate-700 text-slate-200 text-sm font-medium transition"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirmImport}
            disabled={!parseResult || !parseResult.success || isSaving}
            className="min-h-[44px] px-5 py-2.5 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:bg-slate-800 disabled:text-slate-500 disabled:cursor-not-allowed text-white text-sm font-medium font-mono shadow-sm transition flex items-center gap-2"
          >
            {isSaving ? (
              <RefreshCw className="w-4 h-4 animate-spin" />
            ) : (
              <Upload className="w-4 h-4" />
            )}
            <span>{isSaving ? 'Importing & Refreshing...' : 'Import & Refresh Snapshots'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
