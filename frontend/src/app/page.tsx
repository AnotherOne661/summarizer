'use client';

import { useState, useEffect } from 'react';
import { 
  Download, Upload, FileText, Loader2, 
  Moon, Sun, MessageSquare, CheckCircle, 
  AlertCircle, BookOpen, Sparkles 
} from 'lucide-react';

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [fileId, setFileId] = useState<string | null>(null);
  const [filename, setFilename] = useState('');
  const [summary, setSummary] = useState('');
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingQuestion, setLoadingQuestion] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [activeTab, setActiveTab] = useState<'upload' | 'summary' | 'qa'>('upload');
  const [darkMode, setDarkMode] = useState(false);
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [loadingExtract, setLoadingExtract] = useState(false);

  // Detect system preference for dark mode
  useEffect(() => {
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    setDarkMode(isDark);
    if (isDark) {
      document.documentElement.classList.add('dark');
    }
  }, []);

  const toggleDarkMode = () => {
    setDarkMode(!darkMode);
    document.documentElement.classList.toggle('dark');
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Please select a PDF file');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess(false);
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Error uploading PDF');
      }
      
      setFileId(data.file_id);
      setFilename(data.filename);
      setSuccess(true);
      setShowSuccessModal(true);
      
      // Close modal automatically after 3 seconds
      setTimeout(() => setShowSuccessModal(false), 3000);
      
    } catch (error) {
      console.error('Error:', error);
      setError(error instanceof Error ? error.message : 'Error processing PDF');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateSummary = async () => {
    if (!fileId) return;
    
    setLoadingSummary(true);
    setError('');
    
    try {
      const res = await fetch(`/api/summarize/${fileId}`, {
        method: 'POST',
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Error generating summary');
      }
      
      setSummary(data.summary);
      
    } catch (error) {
      console.error('Error:', error);
      // Provide a clearer message if the fetch failed due to network/timeout.
      if (
        error instanceof TypeError &&
        /failed to fetch/i.test(error.message)
      ) {
        setError(
          'Network error: connection was interrupted. The summary may still be generating on the server; you can refresh or try again later.'
        );
      } else {
        setError(error instanceof Error ? error.message : 'Error generating summary');
      }
    } finally {
      setLoadingSummary(false);
    }
  };

  const handleAskQuestion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fileId || !question.trim()) return;
    
    setLoadingQuestion(true);
    setError('');
    setAnswer('');
    
    const formData = new URLSearchParams();
    formData.append('file_id', fileId);
    formData.append('question', question);
    
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString(),
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Error processing question');
      }
      
      setAnswer(data.answer);
      
    } catch (error) {
      console.error('Error:', error);
      if (
        error instanceof TypeError &&
        /failed to fetch/i.test(error.message)
      ) {
        setError(
          'Network error: connection was interrupted while asking a question. Try again later.'
        );
      } else {
        setError(error instanceof Error ? error.message : 'Error processing question');
      }
    } finally {
      setLoadingQuestion(false);
    }
  };
const handleExtractFullText = async () => {
  if (!fileId) return;
  
  setLoadingExtract(true);
  setError('');
  
  try {
    const res = await fetch(`/api/extract/${fileId}`, {
      method: 'GET',
    });
    
    // Verificar si la respuesta es JSON
    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      // Si no es JSON, leer como texto para obtener el mensaje de error
      const text = await res.text();
      throw new Error(`Unexpected response: ${text.substring(0, 100)}`);
    }
    
    const data = await res.json();
    
    if (!res.ok) {
      throw new Error(data.detail || `Error ${res.status}: ${res.statusText}`);
    }
    
    if (!data.full_text) {
      throw new Error('No text content in response');
    }
    
    // Crear y descargar archivo
    const blob = new Blob([data.full_text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `full_text_${filename.replace('.pdf', '')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    
  } catch (error) {
    console.error('Error extracting full text:', error);
    setError(error instanceof Error ? error.message : 'Error extracting full text');
  } finally {
    setLoadingExtract(false);
  }
};

  const handleDownloadTxt = () => {
    if (!summary) return;
    
    const blob = new Blob([summary], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `summary_${filename.replace('.pdf', '')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="min-h-screen bg-stone-50 dark:bg-zinc-950 transition-colors duration-300">
      {/* Success modal */}
      {showSuccessModal && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-white dark:bg-zinc-900 border-l-4 border-emerald-500 rounded shadow-xl p-4 flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
            <p className="text-zinc-800 dark:text-zinc-200 font-medium">PDF uploaded successfully</p>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-4 py-12">
        {/* Header with title and theme toggle */}
        <div className="flex justify-between items-end mb-12 border-b border-stone-200 dark:border-zinc-800 pb-8">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-zinc-900 dark:bg-zinc-100 rounded-lg">
              <FileText className="w-8 h-8 text-white dark:text-zinc-900" />
            </div>
            <div>
              <h1 className="text-4xl font-serif font-bold text-zinc-900 dark:text-zinc-50">
                Smart Reader
              </h1>
              <p className="text-zinc-500 dark:text-zinc-400 mt-1 italic">
                PDF document analysis and synthesis
              </p>
            </div>
          </div>
          <button
            onClick={toggleDarkMode}
            className="p-2.5 hover:bg-stone-200 dark:hover:bg-zinc-800 rounded-full transition-all border border-stone-200 dark:border-zinc-800"
            aria-label="Toggle theme"
          >
            {darkMode ? (
              <Sun className="w-5 h-5 text-orange-300" />
            ) : (
              <Moon className="w-5 h-5 text-zinc-600" />
            )}
          </button>
        </div>

        {/* Minimalist tabs */}
        <div className="flex gap-8 mb-8 border-b border-stone-200 dark:border-zinc-800">
          <button
            onClick={() => setActiveTab('upload')}
            className={`pb-4 px-2 font-medium transition-all relative ${
              activeTab === 'upload' 
                ? 'text-indigo-600 dark:text-indigo-400 after:absolute after:bottom-0 after:left-0 after:w-full after:h-0.5 after:bg-indigo-600' 
                : 'text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-300'
            }`}
          >
            Upload File
          </button>
          <button
            onClick={() => setActiveTab('summary')}
            disabled={!fileId}
            className={`pb-4 px-2 font-medium transition-all relative ${
              activeTab === 'summary' && fileId
                ? 'text-indigo-600 dark:text-indigo-400 after:absolute after:bottom-0 after:left-0 after:w-full after:h-0.5 after:bg-indigo-600' 
                : 'text-zinc-400 cursor-not-allowed'
            }`}
          >
            Executive Summary
          </button>
          <button
            onClick={() => setActiveTab('qa')}
            disabled={!fileId}
            className={`pb-4 px-2 font-medium transition-all relative ${
              activeTab === 'qa' && fileId
                ? 'text-indigo-600 dark:text-indigo-400 after:absolute after:bottom-0 after:left-0 after:w-full after:h-0.5 after:bg-indigo-600' 
                : 'text-zinc-400 cursor-not-allowed'
            }`}
          >
            Queries
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-950/20 border border-red-100 dark:border-red-900/50 rounded-lg flex items-start gap-3 animate-fade-in">
            <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800 dark:text-red-400 font-medium">{error}</p>
          </div>
        )}

        {/* Tab: Upload */}
        {activeTab === 'upload' && (
          <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-sm p-10 border border-stone-200 dark:border-zinc-800">
            <form onSubmit={handleUpload}>
              <div className="border-2 border-dashed border-stone-200 dark:border-zinc-800 rounded-xl p-16 text-center hover:border-indigo-300 dark:hover:border-indigo-900 transition-colors bg-stone-50/50 dark:bg-zinc-950/50">
                <Upload className="mx-auto h-12 w-12 text-stone-400 dark:text-zinc-600 mb-4" />
                <div className="relative">
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileChange}
                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  />
                  <p className="text-xl font-medium text-zinc-800 dark:text-zinc-200">
                    {file ? file.name : 'Select a PDF document'}
                  </p>
                  <p className="text-sm text-zinc-500 dark:text-zinc-500 mt-2">
                    {file 
                      ? `${(file.size / 1024 / 1024).toFixed(2)} MB` 
                      : 'Up to 50MB for deep processing'}
                  </p>
                </div>
              </div>
              <button
                type="submit"
                disabled={!file || loading}
                className="mt-8 w-full bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 py-4 px-6 rounded-lg font-semibold hover:bg-zinc-800 dark:hover:bg-white disabled:bg-stone-300 dark:disabled:bg-zinc-800 transition-all"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    Processing...
                  </span>
                ) : (
                  'Import Document'
                )}
              </button>
            </form>
          </div>
        )}

              {/* Tab: Summary */}
        {activeTab === 'summary' && fileId && (
          <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-sm p-10 border border-stone-200 dark:border-zinc-800">
            <div className="flex justify-between items-center mb-10 flex-wrap gap-4">
              <h2 className="text-2xl font-serif font-bold text-zinc-900 dark:text-white flex items-center gap-3">
                <BookOpen className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
                Executive Summary
              </h2>
              <div className="flex gap-4 flex-wrap">
                {summary && (
                  <button
                    onClick={handleDownloadTxt}
                    className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400 hover:text-indigo-600 border border-stone-200 dark:border-zinc-800 px-4 py-2 rounded-lg transition-colors"
                    title="Download summary as text file"
                  >
                    <Download className="w-4 h-4" />
                    Export Summary
                  </button>
                )}
                <button
                  onClick={handleExtractFullText}
                  disabled={loadingExtract}
                  className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400 hover:text-indigo-600 border border-stone-200 dark:border-zinc-800 px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="Download all short summaries as a text file"
                >
                  <FileText className="w-4 h-4" />
                  {loadingExtract ? 'Downloading...' : 'Download All Summaries'}
                </button>
                <button
                  onClick={handleGenerateSummary}
                  disabled={loadingSummary}
                  className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-lg disabled:bg-stone-300 transition-colors"
                  title={summary ? 'Regenerate summary' : 'Generate summary from document'}
                >
                  {loadingSummary ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  {summary ? 'Refresh' : 'Generate Summary'}
                </button>
              </div>
            </div>

            {loadingSummary && !summary && (
              <div className="py-20 text-center">
                <Loader2 className="w-10 h-10 animate-spin mx-auto mb-4 text-indigo-600" />
                <p className="text-zinc-500 font-serif italic">Drafting summary...</p>
              </div>
            )}

            {summary ? (
              <div className="max-w-3xl mx-auto">
                <div className="prose dark:prose-invert max-w-none">
                  <p className="text-zinc-800 dark:text-zinc-200 whitespace-pre-wrap leading-relaxed font-serif text-lg">
                    {summary}
                  </p>
                </div>
                <div className="mt-8 pt-8 border-t border-stone-100 dark:border-zinc-800 flex justify-end gap-6 text-xs uppercase tracking-widest text-zinc-400">
                  <span>{summary.split(' ').length} words</span>
                  <span>{summary.length} characters</span>
                </div>
              </div>
            ) : !loadingSummary && (
              <div className="py-20 text-center border-2 border-dotted border-stone-100 dark:border-zinc-800 rounded-xl">
                <p className="text-stone-400 italic">Ready to generate document analysis.</p>
              </div>
            )}
          </div>
        )}

        {/* Tab: Questions */}
        {activeTab === 'qa' && fileId && (
          <div className="bg-white dark:bg-zinc-900 rounded-lg shadow-sm p-10 border border-stone-200 dark:border-zinc-800">
            <h2 className="text-2xl font-serif font-bold text-zinc-900 dark:text-white flex items-center gap-3 mb-8">
              <MessageSquare className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
              Direct Query
            </h2>

            <form onSubmit={handleAskQuestion} className="mb-10">
              <div className="flex gap-2 p-1 bg-stone-100 dark:bg-zinc-950 rounded-xl border border-stone-200 dark:border-zinc-800">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="What is the main thesis of the text?"
                  className="flex-1 px-4 py-3 bg-transparent text-zinc-900 dark:text-white focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!question.trim() || loadingQuestion}
                  className="bg-zinc-900 dark:bg-indigo-600 text-white px-8 py-3 rounded-lg font-medium hover:bg-zinc-800 transition-colors"
                >
                  {loadingQuestion ? 'Searching...' : 'Ask'}
                </button>
              </div>
            </form>

            {answer && (
              <div className="bg-stone-50 dark:bg-zinc-950 rounded-lg p-8 border-l-4 border-indigo-500 animate-fade-in">
                <p className="text-zinc-800 dark:text-zinc-200 leading-relaxed text-lg">
                  {answer}
                </p>
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        {fileId && (
          <div className="mt-12 text-center">
            <span className="text-xs uppercase tracking-[0.2em] text-stone-400 dark:text-zinc-600">
              File in memory: <span className="text-zinc-600 dark:text-zinc-400">{filename}</span>
            </span>
          </div>
        )}
      </div>
    </main>
  );
}