import React, { useState, useEffect } from 'react';

export default function SettingsTab() {
  const [settings, setSettings] = useState(null);
  const [inputs, setInputs] = useState({
    gemini_key: '',
    fred_key: '',
    discord_webhook: ''
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [apiSecret, setApiSecret] = useState(() => localStorage.getItem('quantos_api_key') || '');

  const fetchSettings = async () => {
    try {
      const res = await fetch('/api/settings');
      if (res.ok) {
        const json = await res.json();
        setSettings(json);
      }
    } catch (e) {
      console.error("Failed to fetch settings");
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    
    // Only send fields that the user actually typed into
    const payload = {};
    if (inputs.gemini_key) payload.gemini_key = inputs.gemini_key;
    if (inputs.fred_key) payload.fred_key = inputs.fred_key;
    if (inputs.discord_webhook) payload.discord_webhook = inputs.discord_webhook;
    
    try {
      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'X-Api-Key': localStorage.getItem('quantos_api_key') || ''
        },
        body: JSON.stringify(payload)
      });
      
      if (res.ok) {
        setSaveSuccess(true);
        setInputs({ gemini_key: '', fred_key: '', discord_webhook: '' }); // Clear inputs after save
        await fetchSettings(); // Refresh masked keys
        
        setTimeout(() => setSaveSuccess(false), 3000); // Hide success message after 3s
      }
    } catch (e) {
      console.error("Failed to save settings", e);
    } finally {
      setIsSaving(false);
    }
    // Save API secret to localStorage
    localStorage.setItem('quantos_api_key', apiSecret);
  };

  if (!settings) {
    return <div className="glass-panel" style={{ textAlign: 'center', padding: '40px' }}>Loading settings...</div>;
  }

  return (
    <div className="grid-layout">
      
      <div className="glass-panel col-span-12 animate-fade-in delay-1" style={{ maxWidth: '800px', margin: '0 auto' }}>
        <h2 style={{ marginBottom: '24px' }}> System Configuration</h2>
        
        <p className="text-muted" style={{ marginBottom: '32px', fontSize: '0.9rem' }}>
          Configure API credentials and external service integrations. Keys are masked for security. 
          To update a key, enter the new value and click Save. Leave blank to keep the existing key.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          
          {/* Gemini API Key */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <label style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
               Google Gemini API Key
            </label>
            <p className="text-muted" style={{ fontSize: '0.8rem' }}>Used for the LLM Macro Sentiment Agent.</p>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <input 
                type="password"
                placeholder={settings.has_gemini ? `Current: ${settings.gemini_key_masked}` : "Enter API Key..."}
                value={inputs.gemini_key}
                onChange={(e) => setInputs({...inputs, gemini_key: e.target.value})}
                style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white', fontFamily: 'monospace' }}
              />
              {settings.has_gemini && <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}> Active</span>}
            </div>
          </div>

          {/* FRED API Key */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
            <label style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
               FRED API Key
            </label>
            <p className="text-muted" style={{ fontSize: '0.8rem' }}>Used to fetch Federal Reserve economic data like the Yield Curve.</p>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <input 
                type="password"
                placeholder={settings.has_fred ? `Current: ${settings.fred_key_masked}` : "Enter API Key..."}
                value={inputs.fred_key}
                onChange={(e) => setInputs({...inputs, fred_key: e.target.value})}
                style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white', fontFamily: 'monospace' }}
              />
              {settings.has_fred && <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}> Active</span>}
            </div>
          </div>

          {/* Discord Webhook */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
            <label style={{ fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '8px' }}>
               Discord Webhook URL
            </label>
            <p className="text-muted" style={{ fontSize: '0.8rem' }}>Used by the Paper Trader to push execution alerts to your Discord channel.</p>
            <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
              <input 
                type="password"
                placeholder={settings.has_webhook ? `Current: ${settings.discord_webhook_masked}` : "Enter Webhook URL..."}
                value={inputs.discord_webhook}
                onChange={(e) => setInputs({...inputs, discord_webhook: e.target.value})}
                style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(0,0,0,0.2)', color: 'white', fontFamily: 'monospace' }}
              />
              {settings.has_webhook && <span style={{ color: 'var(--success)', fontSize: '0.85rem' }}> Active</span>}
            </div>
          </div>

        </div>
        
        {/* Actions */}
        <div style={{ marginTop: '40px', display: 'flex', alignItems: 'center', gap: '24px' }}>
          <button 
            onClick={handleSave}
            disabled={isSaving || (!inputs.gemini_key && !inputs.fred_key && !inputs.discord_webhook)}
            style={{ 
              padding: '12px 24px', 
              borderRadius: '8px', 
              border: 'none', 
              cursor: (!inputs.gemini_key && !inputs.fred_key && !inputs.discord_webhook) ? 'not-allowed' : 'pointer', 
              fontWeight: 'bold', 
              background: (!inputs.gemini_key && !inputs.fred_key && !inputs.discord_webhook) ? 'rgba(255,255,255,0.1)' : 'var(--accent-blue)',
              color: (!inputs.gemini_key && !inputs.fred_key && !inputs.discord_webhook) ? 'var(--text-muted)' : 'white',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}
          >

            Save Settings
          </button>
          
          {saveSuccess && (
            <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 'bold' }}>
               Configuration Saved Successfully!
            </span>
          )}
        </div>

      </div>
    </div>
  );
}
