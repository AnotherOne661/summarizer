'use client';

import { useState } from 'react';
import { Download, Upload, FileText, Loader2 } from 'lucide-react';

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
  const [activeTab, setActiveTab] = useState<'upload' | 'summary' | 'qa'>('upload');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError('');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError('Por favor, selecciona un archivo PDF');
      return;
    }

    setLoading(true);
    setError('');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || 'Error al subir el PDF');
      }
      
      setFileId(data.file_id);
      setFilename(data.filename);
      setActiveTab('summary');
      alert("PDF subido correctamente. Pendiente hacer un modal")      
    } catch (error) {
      console.error('Error:', error);
      setError(error instanceof Error ? error.message : 'Error al procesar el PDF');
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
        throw new Error(data.detail || 'Error al generar resumen');
      }
      
      setSummary(data.summary);
      
    } catch (error) {
      console.error('Error:', error);
      setError(error instanceof Error ? error.message : 'Error al generar el resumen');
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
        throw new Error(data.detail || 'Error al procesar la pregunta');
      }
      
      setAnswer(data.answer);
      
    } catch (error) {
      console.error('Error:', error);
      setError(error instanceof Error ? error.message : 'Error al procesar la pregunta');
    } finally {
      setLoadingQuestion(false);
    }
  };

  const handleDownloadTxt = () => {
    if (!summary) return;
    
    const blob = new Blob([summary], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `resumen_${filename.replace('.pdf', '')}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-4 py-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-8">
          Resumidor de PDF con IA
        </h1>

        {/* Tabs */}
        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setActiveTab('upload')}
            className={`px-4 py-2 rounded-lg ${
              activeTab === 'upload' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gray-200 text-gray-700'
            }`}
          >
             Subir PDF
          </button>
          <button
            onClick={() => setActiveTab('summary')}
            disabled={!fileId}
            className={`px-4 py-2 rounded-lg ${
              activeTab === 'summary' && fileId
                ? 'bg-blue-600 text-white' 
                : fileId 
                  ? 'bg-gray-200 text-gray-700' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
            Resumen
          </button>
          <button
            onClick={() => setActiveTab('qa')}
            disabled={!fileId}
            className={`px-4 py-2 rounded-lg ${
              activeTab === 'qa' && fileId
                ? 'bg-blue-600 text-white' 
                : fileId 
                  ? 'bg-gray-200 text-gray-700' 
                  : 'bg-gray-100 text-gray-400 cursor-not-allowed'
            }`}
          >
           Preguntas
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
            {error}
          </div>
        )}

        {/* Tab: Upload */}
        {activeTab === 'upload' && (
          <div className="bg-white rounded-lg shadow p-6">
            <form onSubmit={handleUpload}>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
                <Upload className="mx-auto h-12 w-12 text-gray-400 mb-4" />
                <input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                  className="mb-4"
                />
                {file && (
                  <p className="text-sm text-gray-600">
                    Archivo: {file.name} ({(file.size / 1024 / 1024).toFixed(2)} MB)
                  </p>
                )}
              </div>
              <button
                type="submit"
                disabled={!file || loading}
                className="mt-4 w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
              >
                {loading ? 'Subiendo...' : 'Subir PDF'}
              </button>
            </form>
          </div>
        )}

        {/* Tab: Summary */}
        {activeTab === 'summary' && fileId && (
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Resumen</h2>
              <div className="flex gap-2">
                {summary && (
                  <button
                    onClick={handleDownloadTxt}
                    className="flex items-center gap-2 bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700"
                  >
                    <Download className="w-4 h-4" />
                    Descargar
                  </button>
                )}
                <button
                  onClick={handleGenerateSummary}
                  disabled={loadingSummary}
                  className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
                >
                  {loadingSummary ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generando...
                    </>
                  ) : (
                    'Generar Resumen'
                  )}
                </button>
              </div>
            </div>
            {summary ? (
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="whitespace-pre-wrap">{summary}</p>
              </div>
            ) : (
              <p className="text-gray-500 text-center py-8">
                Haz clic en "Generar Resumen" para obtener un resumen del documento.
              </p>
            )}
          </div>
        )}

        {/* Tab: Questions */}
        {activeTab === 'qa' && fileId && (
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Preguntas</h2>
            <form onSubmit={handleAskQuestion} className="mb-6">
              <div className="flex gap-2">
                <input
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ej: ¿De qué trata el libro?"
                  className="flex-1 border border-gray-300 rounded-lg px-4 py-2"
                />
                <button
                  type="submit"
                  disabled={!question.trim() || loadingQuestion}
                  className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-400"
                >
                  {loadingQuestion ? 'Enviando...' : 'Preguntar'}
                </button>
              </div>
            </form>
            {answer && (
              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="font-semibold mb-2">Respuesta:</p>
                <p>{answer}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}