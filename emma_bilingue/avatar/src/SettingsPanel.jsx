import React, { useState, useEffect } from 'react';

export function SettingsPanel({ onClose }) {
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [status, setStatus] = useState('');
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    // Cargar desde localStorage
    const saved = localStorage.getItem('OPENROUTER_API_KEY');
    if (saved) setApiKey(saved);
  }, []);

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setStatus({ type: 'error', msg: 'La clave no puede estar vacía' });
      return;
    }

    localStorage.setItem('OPENROUTER_API_KEY', apiKey.trim());
    setStatus({ type: 'success', msg: 'Clave guardada localmente' });
    
    // Opcional: también intentar guardarla en .env si hay permisos
    try {
      await fetch('/api/save-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: apiKey.trim() })
      });
    } catch (e) {
      // Ignorar si no hay backend
    }
  };

  const handleTest = async () => {
    if (!apiKey.trim()) {
      setStatus({ type: 'error', msg: 'Primero ingresa una clave' });
      return;
    }

    setTesting(true);
    setStatus({ type: 'info', msg: 'Probando conexión...' });

    try {
      const response = await fetch('https://openrouter.ai/api/v1/models', {
        headers: {
          'Authorization': `Bearer ${apiKey.trim()}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        const modelCount = data.data?.length || 0;
        setStatus({ 
          type: 'success', 
          msg: `✓ Conexión exitosa - ${modelCount} modelos disponibles` 
        });
      } else {
        const error = await response.text();
        setStatus({ 
          type: 'error', 
          msg: `✗ Error ${response.status}: ${error}` 
        });
      }
    } catch (e) {
      setStatus({ type: 'error', msg: `✗ Error de red: ${e.message}` });
    } finally {
      setTesting(false);
    }
  };

  const handleClear = () => {
    localStorage.removeItem('OPENROUTER_API_KEY');
    setApiKey('');
    setStatus({ type: 'info', msg: 'Clave eliminada' });
  };

  return (
    <div className="settings-panel">
      <div className="settings-header">
        <h2>⚙️ Configuración</h2>
        <button className="close-btn" onClick={onClose}>✕</button>
      </div>

      <div className="settings-section">
        <h3>🔑 OpenRouter API Key</h3>
        <p className="help-text">
          Necesaria para el modelo LLM (Gemma-4-12b). 
          <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">Obtener clave</a>
        </p>

        <div className="input-group">
          <input
            type={showKey ? 'text' : 'password'}
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="sk-or-xxxxxxxxxxxx"
            className="api-key-input"
          />
          <button 
            type="button" 
            className="toggle-btn"
            onClick={() => setShowKey(!showKey)}
            aria-label={showKey ? 'Ocultar clave' : 'Mostrar clave'}
          >
            {showKey ? '🙈' : '👁'}
          </button>
        </div>

        <div className="button-row">
          <button className="btn btn-primary" onClick={handleTest} disabled={testing}>
            {testing ? '⏳ Probando...' : '🧪 Probar Conexión'}
          </button>
          <button className="btn btn-success" onClick={handleSave}>
            💾 Guardar
          </button>
          <button className="btn btn-danger" onClick={handleClear}>
            🗑️ Borrar
          </button>
        </div>

        {status && (
          <div className={`status-message ${status.type}`}>
            {status.msg}
          </div>
        )}
      </div>

      <div className="settings-section">
        <h3>🎤 Audio</h3>
        <label>
          <input type="checkbox" defaultChecked /> Half-duplex (micrófono off mientras habla Emma)
        </label>
        <label>
          <input type="checkbox" defaultChecked /> Post-TTS delay (500ms)
        </label>
      </div>

      <div className="settings-section">
        <h3>🤖 Modelo LLM</h3>
        <select defaultValue="google/gemma-4-12b">
          <option value="google/gemma-4-12b">Gemma 4 12B (Recomendado, gratis)</option>
          <option value="google/gemma-4-26b-a4b-it">Gemma 4 26B MoE</option>
          <option value="openrouter/auto">Auto (OpenRouter decide)</option>
        </select>
      </div>

      <div className="settings-footer">
        <button className="btn btn-secondary" onClick={onClose}>Cerrar</button>
      </div>
    </div>
  );
}

export default SettingsPanel;