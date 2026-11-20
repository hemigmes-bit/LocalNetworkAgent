with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Add CSS for settings button and modal
css_to_add = """
    .btn-settings {
      background: rgba(102, 126, 234, 0.3);
      border-color: rgba(102, 126, 234, 0.6);
    }
    .btn-settings:hover { background: rgba(102, 126, 234, 0.5); }

    /* Settings Modal */
    .modal-overlay {
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.8);
      z-index: 1000;
      display: flex;
      align-items: center;
      justify-content: center;
      opacity: 0;
      visibility: hidden;
      transition: all 0.3s ease;
    }
    .modal-overlay.open {
      opacity: 1;
      visibility: visible;
    }
    .modal {
      background: #1a1a2e;
      border: 1px solid rgba(102, 126, 234, 0.3);
      border-radius: 16px;
      padding: 24px;
      width: 90%;
      max-width: 480px;
      max-height: 80vh;
      overflow-y: auto;
      transform: scale(0.9);
      transition: transform 0.3s ease;
    }
    .modal-overlay.open .modal {
      transform: scale(1);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid rgba(102, 126, 234, 0.2);
    }
    .modal h2 { margin: 0; color: #667eea; }
    .modal-close {
      background: none;
      border: none;
      color: #888;
      font-size: 24px;
      cursor: pointer;
      padding: 4px 8px;
    }
    .modal-close:hover { color: #fff; }
    
    .settings-section {
      margin-bottom: 20px;
    }
    .settings-section h3 {
      color: #667eea;
      font-size: 14px;
      margin-bottom: 12px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .help-text {
      font-size: 12px;
      color: #888;
      margin-bottom: 12px;
    }
    .help-text a { color: #60a5fa; }
    
    .input-group {
      display: flex;
      gap: 8px;
    }
    .api-key-input {
      flex: 1;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(102, 126, 234, 0.3);
      border-radius: 8px;
      padding: 12px 16px;
      color: #fff;
      font-family: monospace;
      font-size: 13px;
    }
    .api-key-input:focus { outline: none; border-color: #667eea; }
    .toggle-btn {
      background: rgba(102, 126, 234, 0.2);
      border: 1px solid rgba(102, 126, 234, 0.3);
      border-radius: 8px;
      padding: 8px 12px;
      cursor: pointer;
      color: #fff;
    }
    
    .button-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 12px;
    }
    .btn {
      background: rgba(102, 126, 234, 0.2);
      border: 1px solid rgba(102, 126, 234, 0.5);
      color: #fff;
      padding: 10px 16px;
      border-radius: 8px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s;
    }
    .btn:hover { background: rgba(102, 126, 234, 0.4); }
    .btn:disabled { opacity: 0.5; cursor: not-allowed; }
    .btn-primary { background: #667eea; border-color: #667eea; }
    .btn-success { background: #10b981; border-color: #10b981; }
    .btn-danger { background: #ef4444; border-color: #ef4444; }
    .btn-secondary { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.2); }
    
    .status-message {
      padding: 10px 12px;
      border-radius: 8px;
      font-size: 12px;
      margin-top: 12px;
    }
    .status-message.success { background: rgba(16, 185, 129, 0.2); border: 1px solid #10b981; color: #10b981; }
    .status-message.error { background: rgba(239, 68, 68, 0.2); border: 1px solid #ef4444; color: #ef4444; }
    .status-message.info { background: rgba(96, 165, 250, 0.2); border: 1px solid #60a5fa; color: #60a5fa; }
    
    .settings-section label {
      display: block;
      margin: 8px 0;
      color: #ddd;
      font-size: 13px;
      cursor: pointer;
    }
    .settings-section select {
      width: 100%;
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(102, 126, 234, 0.3);
      border-radius: 8px;
      padding: 10px 12px;
      color: #fff;
      font-size: 13px;
    }
    
    .settings-footer {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid rgba(102, 126, 234, 0.2);
      text-align: right;
    }
"""

# Add CSS before </style>
idx = content.find('</style>')
if idx >= 0:
    content = content[:idx] + css_to_add + content[idx:]

# Add modal HTML before </body>
modal_html = """
  <!-- Settings Modal -->
  <div class="modal-overlay" id="settings-modal">
    <div class="modal">
      <div class="modal-header">
        <h2>⚙️ Configuración</h2>
        <button class="modal-close" onclick="closeSettings()">&times;</button>
      </div>
      
      <div class="settings-section">
        <h3>🔑 OpenRouter API Key</h3>
        <p class="help-text">
          Necesaria para el modelo LLM (Gemma-4-12b). 
          <a href="https://openrouter.ai/keys" target="_blank" rel="noopener">Obtener clave</a>
        </p>
        <div class="input-group">
          <input type="password" id="api-key-input" placeholder="sk-or-xxxxxxxxxxxx" class="api-key-input">
          <button class="toggle-btn" onclick="toggleKeyVisibility()" aria-label="Mostrar/Ocultar">👁</button>
        </div>
        <div class="button-row">
          <button class="btn btn-primary" onclick="testApiKey()" id="btn-test">🧪 Probar Conexión</button>
          <button class="btn btn-success" onclick="saveApiKey()">💾 Guardar</button>
          <button class="btn btn-danger" onclick="clearApiKey()">🗑️ Borrar</button>
        </div>
        <div id="api-status"></div>
      </div>
      
      <div class="settings-section">
        <h3>🎤 Audio</h3>
        <label><input type="checkbox" id="half-duplex" checked> Half-duplex (micrófono off mientras habla Emma)</label>
        <label><input type="checkbox" id="post-tts-delay" checked> Post-TTS delay (500ms)</label>
      </div>
      
      <div class="settings-section">
        <h3>🤖 Modelo LLM</h3>
        <select id="model-select">
          <option value="google/gemma-4-12b">Gemma 4 12B (Recomendado, gratis)</option>
          <option value="google/gemma-4-26b-a4b-it">Gemma 4 26B MoE</option>
          <option value="openrouter/auto">Auto (OpenRouter decide)</option>
        </select>
      </div>
      
      <div class="settings-footer">
        <button class="btn btn-secondary" onclick="closeSettings()">Cerrar</button>
      </div>
    </div>
  </div>
"""

idx = content.find('</body>')
if idx >= 0:
    content = content[:idx] + modal_html + content[idx:]

# Add JavaScript functions for settings modal
js_functions = """

// Settings Modal Functions
function openSettings() {
  document.getElementById('settings-modal').classList.add('open');
  // Load saved API key
  const saved = localStorage.getItem('OPENROUTER_API_KEY');
  if (saved) document.getElementById('api-key-input').value = saved;
}

function closeSettings() {
  document.getElementById('settings-modal').classList.remove('open');
}

function toggleKeyVisibility() {
  const input = document.getElementById('api-key-input');
  const btn = event.target;
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
  }
}

async function testApiKey() {
  const key = document.getElementById('api-key-input').value.trim();
  const statusDiv = document.getElementById('api-status');
  const btn = document.getElementById('btn-test');
  
  if (!key) {
    statusDiv.innerHTML = '<div class="status-message error">✗ La clave no puede estar vacía</div>';
    return;
  }
  
  btn.disabled = true;
  btn.textContent = '⏳ Probando...';
  statusDiv.innerHTML = '<div class="status-message info">Probando conexión...</div>';
  
  try {
    const response = await fetch('https://openrouter.ai/api/v1/models', {
      headers: {
        'Authorization': 'Bearer ' + key,
        'Content-Type': 'application/json'
      }
    });
    
    if (response.ok) {
      const data = await response.json();
      const count = data.data?.length || 0;
      statusDiv.innerHTML = '<div class="status-message success">✓ Conexión exitosa - ' + count + ' modelos disponibles</div>';
    } else {
      const error = await response.text();
      statusDiv.innerHTML = '<div class="status-message error">✗ Error ' + response.status + ': ' + error + '</div>';
    }
  } catch (e) {
    statusDiv.innerHTML = '<div class="status-message error">✗ Error de red: ' + e.message + '</div>';
  } finally {
    btn.disabled = false;
    btn.textContent = '🧪 Probar Conexión';
  }
}

function saveApiKey() {
  const key = document.getElementById('api-key-input').value.trim();
  const statusDiv = document.getElementById('api-status');
  
  if (!key) {
    statusDiv.innerHTML = '<div class="status-message error">✗ La clave no puede estar vacía</div>';
    return;
  }
  
  localStorage.setItem('OPENROUTER_API_KEY', key);
  statusDiv.innerHTML = '<div class="status-message success">💾 Clave guardada localmente</div>';
  
  // Also try to save via backend if available
  try {
    await fetch('/api/save-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: key })
    });
  } catch (e) {
    // Ignore if no backend
  }
}

function clearApiKey() {
  localStorage.removeItem('OPENROUTER_API_KEY');
  document.getElementById('api-key-input').value = '';
  document.getElementById('api-status').innerHTML = '<div class="status-message info">🗑️ Clave eliminada</div>';
}

// Close modal on overlay click
document.getElementById('settings-modal').addEventListener('click', function(e) {
  if (e.target === this) closeSettings();
});

// Close on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') closeSettings();
});
"""

# Add JS functions before the simulateAudio function
idx = content.find('function simulateAudio()')
if idx >= 0:
    content = content[:idx] + js_functions + '\n' + content[idx:]

# Write back
with open(r'C:\Users\Usuario\LocalNetworkAgent\emma_bilingue\avatar\index.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")