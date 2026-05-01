import React, { useState, useEffect, useRef } from 'react';
import {
  Play, Square, Activity, TrendingUp, ShieldCheck,
  Settings as SettingsIcon, Bell, ChevronRight, Info, AlertTriangle,
  Cpu, Zap, BarChart3, Database, Megaphone
} from 'lucide-react';
import './index.css';

interface Signal {
  time: string;
  symbol: string;
  type: 'BUY' | 'SELL';
  strategy: string;
  source: string;
}

const API_BASE = "http://localhost:8000";
const QUANTUM_API = "http://127.0.0.1:8080";

function App() {
  const [status, setStatus] = useState({
    is_running: false,
    pid: null,
    uptime: null,
    account_status: 'Checking...',
    telegram_status: 'Checking...',
    mega_grid_active: true,
    polimata_retrains: 0,
    last_retrain: null
  });
  const [stats, setStats] = useState({
    daily_pnl: 0,
    total_pnl: 0,
    equity: 0,
    balance: 0,
    active_trades: 0,
    polimata_retrains: 0,
    margin: 0,
    free_margin: 0,
    margin_level: 0,
    is_micro_sizing: false,
    risk_label: "",
    active_positions: [],
    trade_history: [],
    last_log_lines: []
  });
  const [signals, setSignals] = useState<Signal[]>([]);
  const [creds, setCreds] = useState({ account: '', password: '', server: 'FTMO-Demo' });
  const [risk, setRisk] = useState(0.4);

  const [discoveredAccounts, setDiscoveredAccounts] = useState<any[]>([]);
  const [showNewAccount, setShowNewAccount] = useState(false);
  const [activeTab, setActiveTab] = useState<'mission' | 'binance'>('mission');
  const [binanceData, setBinanceData] = useState<any>({
    account_type: 'Checking...',
    can_trade: false,
    balances: {},
    prices: {},
    active_positions: [],
    last_log_lines: []
  });
  const [fleetConfig, setFleetConfig] = useState<any>({});
  const [affinityMap, setAffinityMap] = useState<any>({}); // [NEW v6.3.2]

  const getIARecommendation = (symbol: string) => {
    if (!affinityMap[symbol]) return "NEUTRAL / BALANZA";
    return affinityMap[symbol].reco || "NEUTRAL / BALANZA";
  };

  const getIAClassText = (symbol: string) => {
    const reco = getIARecommendation(symbol);
    if (reco.includes('NEM1')) return { color: '#00f2ff', textShadow: '0 0 8px rgba(0,242,255,0.4)' };
    if (reco.includes('NEM2')) return { color: '#ff4444', textShadow: '0 0 8px rgba(255,68,68,0.4)' };
    return { color: '#666' };
  };

  const isUpdatingLockRef = useRef(false);
  const [basketConfig, setBasketConfig] = useState({
    enabled: true,
    threshold: 500.0,
    threshold_pct: 2.0,
    last_trigger: null
  });

  const [isUpdatingLock, setIsUpdatingLock] = useState(false);
  const [thresholdInput, setThresholdInput] = useState("");

  const fetchConfig = async () => {
    try {
      const resp = await fetch(`${API_BASE}/config`);
      const config = await resp.json();
      setRisk(config.risk_per_trade * 100);
      if (config.mt5) {
        setCreds({
          account: String(config.mt5.account) || '',
          password: config.mt5.password || '',
          server: config.mt5.server || 'FTMO-Demo'
        });
      }
    } catch (err) {
      console.error("Failed to fetch initial config", err);
    }
  };

  const fetchAccounts = async () => {
    try {
      const resp = await fetch(`${API_BASE}/accounts`);
      const data = await resp.json();
      setDiscoveredAccounts(data);

      if (data.length > 0 && !creds.account) {
        const first = data[0];
        setCreds({ account: String(first.account), server: first.server, password: '' });
        setShowNewAccount(false);
        await fetch(`${API_BASE}/accounts/select`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ account: first.account, server: first.server })
        });
      }
    } catch (err) {
      console.error("Failed to fetch discovered accounts", err);
    }
  };

  const fetchData = async () => {
    try {
      const statusRes = await fetch(`${API_BASE}/status`);
      const statusData = await statusRes.json();
      setStatus(statusData);

      const statsRes = await fetch(`${API_BASE}/stats`);
      const statsData = await statsRes.json();
      setStats(statsData);

      const signalsRes = await fetch(`${API_BASE}/signals`);
      const signalsData = await signalsRes.json();
      setSignals(signalsData);

      const binanceRes = await fetch(`${API_BASE}/binance/stats`);
      const bData = await binanceRes.json();
      setBinanceData(bData);
    } catch (err) {
      console.error("Failed to connect to backend");
    }
  };

  const fetchFleetConfig = async () => {
    try {
      const res = await fetch(`${QUANTUM_API}/config`);
      if (res.ok) {
        const data = await res.json();
        setFleetConfig(data);
      }
    } catch (e) {
      console.error("Failed to fetch fleet config");
    }
  };

  const fetchAffinity = async () => {
    try {
      const res = await fetch(`${QUANTUM_API}/affinity`);
      if (res.ok) {
        const data = await res.json();
        setAffinityMap(data);
      }
    } catch (e) { }
  };

  const fetchBasketConfig = async () => {
    if (isUpdatingLockRef.current) return;
    try {
      // [v6.7.0] Leer Lock % dinámico desde la Quantum API
      const resp = await fetch(`${QUANTUM_API}/system-status`);
      if (resp.ok) {
        const sysData = await resp.json();
        setBasketConfig(prev => ({
          ...prev,
          threshold_pct: sysData.lock_pct || 0.25,
          trust_tier: sysData.trust_tier
        }));
      }
    } catch (err) {
      console.error("Failed to fetch quantum system status", err);
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchAccounts();
    fetchData();
    fetchBasketConfig();
    fetchFleetConfig();
    fetchAffinity();

    const interval = setInterval(() => {
      fetchData();
      fetchBasketConfig();
      fetchFleetConfig();
      fetchAffinity();
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (basketConfig.threshold_pct !== undefined && !isUpdatingLock) {
      setThresholdInput(String(basketConfig.threshold_pct));
    }
  }, [basketConfig.threshold_pct, isUpdatingLock]);

  const handleSelectAccount = async (acc: any) => {
    if (acc === 'new') {
      setShowNewAccount(true);
      return;
    }
    setShowNewAccount(false);
    setCreds({ account: String(acc.account), server: acc.server, password: '' });
    try {
      await fetch(`${API_BASE}/accounts/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account: acc.account, server: acc.server })
      });
    } catch (err) {
      console.error("Failed to switch account", err);
    }
  };

  const handleStart = async () => {
    try {
      await fetch(`${API_BASE}/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          risk_per_trade: risk / 100,
          mt5: creds.account ? creds : null
        })
      });
    } catch (err) {
      alert("Error starting bot");
    }
  };

  const handleStop = async () => {
    try {
      await fetch(`${API_BASE}/stop`, { method: 'POST' });
    } catch (err) {
      alert("Error stopping bot");
    }
  };

  const handleToggleMegaGrid = async () => {
    try {
      const resp = await fetch(`${API_BASE}/config/mega-grid?enabled=${!status.mega_grid_active}`, { method: 'POST' });
      if (resp.ok) {
        setStatus(prev => ({ ...prev, mega_grid_active: !prev.mega_grid_active }));
      }
    } catch (err) {
      console.error("Failed to toggle mega grid", err);
    }
  };

  const handleToggleBasketLock = async () => {
    isUpdatingLockRef.current = true;
    setIsUpdatingLock(true);
    const newConfig = { ...basketConfig, enabled: !basketConfig.enabled };
    setBasketConfig(newConfig);
    try {
      await fetch(`${API_BASE}/api/basket-lock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      setTimeout(() => {
        isUpdatingLockRef.current = false;
        setIsUpdatingLock(false);
      }, 3000);
    } catch (err) {
      console.error("Failed to update basket lock", err);
      isUpdatingLockRef.current = false;
      setIsUpdatingLock(false);
    }
  };

  const handleUpdateThreshold = async () => {
    const threshold_pct = parseFloat(thresholdInput);
    if (isNaN(threshold_pct)) {
      setThresholdInput(String(basketConfig.threshold_pct));
      return;
    }
    isUpdatingLockRef.current = true;
    setIsUpdatingLock(true);
    const newConfig = { ...basketConfig, threshold_pct };
    setBasketConfig(newConfig);
    try {
      await fetch(`${API_BASE}/api/basket-lock`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newConfig)
      });
      setTimeout(() => {
        isUpdatingLockRef.current = false;
        setIsUpdatingLock(false);
      }, 3000);
    } catch (err) {
      console.error("Failed to update basket threshold", err);
      isUpdatingLockRef.current = false;
      setIsUpdatingLock(false);
    }
  };

  const handleFleetToggle = async (symbol: string) => {
    const current = fleetConfig[symbol];
    const newStatus = current.status === 'ON' ? 'OFF' : 'ON';
    const updated = { ...current, status: newStatus };
    
    setFleetConfig((prev: any) => ({ ...prev, [symbol]: updated }));
    
    try {
      await fetch(`${QUANTUM_API}/update/${symbol}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
    } catch (e) { console.error("Fleet sync error"); }
  };

  const handleFleetRoleUpdate = async (symbol: string, role: string) => {
    const current = fleetConfig[symbol];
    const updated = { ...current, manual_nem_role: role, strategy_mode: 'MANUAL' };
    
    setFleetConfig((prev: any) => ({ ...prev, [symbol]: updated }));
    
    try {
      await fetch(`${QUANTUM_API}/update/${symbol}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
    } catch (e) { console.error("Fleet sync error"); }
  };

  const handleFleetModeAuto = async (symbol: string) => {
    const current = fleetConfig[symbol];
    const updated = { ...current, manual_nem_role: null, strategy_mode: 'AUTO' };
    
    setFleetConfig((prev: any) => ({ ...prev, [symbol]: updated }));
    
    try {
      await fetch(`${QUANTUM_API}/update/${symbol}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
    } catch (e) { console.error("Fleet sync error"); }
  };

  return (
    <div className="dashboard-container">
      <aside className="sidebar">
        <div className="logo" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldCheck size={32} color="#00f2ff" />
          <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>QUANTUM</h2>
        </div>

        <nav style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="input-group">
            <label style={{ fontSize: '0.8rem', color: '#a0a0a0' }}>RISK PER TRADE (%)</label>
            <input
              type={stats.is_micro_sizing ? "text" : "number"}
              step="0.1"
              value={stats.is_micro_sizing ? stats.risk_label : risk}
              readOnly={stats.is_micro_sizing}
              onChange={(e) => !stats.is_micro_sizing && setRisk(parseFloat(e.target.value))}
              style={{
                color: stats.is_micro_sizing ? '#ffd700' : 'inherit',
                fontWeight: stats.is_micro_sizing ? 'bold' : 'normal',
                backgroundColor: stats.is_micro_sizing ? 'rgba(255, 215, 0, 0.05)' : 'rgba(255, 255, 255, 0.05)',
                cursor: stats.is_micro_sizing ? 'default' : 'text'
              }}
            />
            {stats.is_micro_sizing && (
              <p style={{ fontSize: '0.65rem', color: '#ffd700', marginTop: '4px', opacity: 0.8 }}>
                Auto-assigned by Protective Protocol
              </p>
            )}
          </div>

          <div className="input-group">
            <label style={{ fontSize: '0.8rem', color: '#a0a0a0' }}>MT5 ACCOUNT SESSIONS</label>
            <select
              className="account-select"
              value={showNewAccount ? 'new' : `${creds.server}|${creds.account}`}
              onChange={(e) => {
                if (e.target.value === 'new') {
                  handleSelectAccount('new');
                } else {
                  const [server, account] = e.target.value.split('|');
                  handleSelectAccount({ server, account });
                }
              }}
              style={{
                width: '100%',
                padding: '10px',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                borderRadius: '8px',
                color: '#fff',
                fontSize: '0.9rem'
              }}
            >
              {discoveredAccounts.map((acc, i) => (
                <option key={i} value={`${acc.server}|${acc.account}`}>
                  {acc.label}
                </option>
              ))}
              <option value="new">+ ADD NEW ACCOUNT</option>
            </select>
          </div>

          <div
            className={`nav-item ${activeTab === 'mission' ? 'active' : ''}`}
            onClick={() => setActiveTab('mission')}
            style={{
              padding: '12px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: activeTab === 'mission' ? 'rgba(0, 242, 255, 0.1)' : 'transparent',
              color: activeTab === 'mission' ? '#00f2ff' : '#888',
              transition: 'all 0.2s'
            }}
          >
            <TrendingUp size={20} />
            <span style={{ fontWeight: 600 }}>MT5 MISSION</span>
          </div>

          <div
            className={`nav-item ${activeTab === 'binance' ? 'active' : ''}`}
            onClick={() => setActiveTab('binance')}
            style={{
              padding: '12px',
              borderRadius: '8px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: activeTab === 'binance' ? 'rgba(255, 215, 0, 0.1)' : 'transparent',
              color: activeTab === 'binance' ? '#ffd700' : '#888',
              transition: 'all 0.2s'
            }}
          >
            <Database size={20} />
            <span style={{ fontWeight: 600 }}>BINANCE TERMINAL</span>
          </div>

          {(showNewAccount || !creds.account) && (
            <>
              <div className="input-group">
                <label style={{ fontSize: '0.8rem', color: '#a0a0a0' }}>ACCOUNT ID</label>
                <input
                  type="text"
                  placeholder="12345678"
                  value={creds.account}
                  onChange={(e) => setCreds({ ...creds, account: e.target.value })}
                />
              </div>

              <div className="input-group">
                <label style={{ fontSize: '0.8rem', color: '#a0a0a0' }}>SERVER</label>
                <input
                  type="text"
                  placeholder="FTMO-Server"
                  value={creds.server}
                  onChange={(e) => setCreds({ ...creds, server: e.target.value })}
                />
              </div>
            </>
          )}

          <div className="input-group">
            <label style={{ fontSize: '0.8rem', color: '#a0a0a0' }}>PASSWORD</label>
            <input
              type="password"
              placeholder="MT5 Password"
              value={creds.password}
              onChange={(e) => setCreds({ ...creds, password: e.target.value })}
              style={{
                border: creds.password ? '1px solid rgba(0, 242, 255, 0.3)' : '1px solid rgba(255, 255, 255, 0.1)'
              }}
            />
            {!creds.password && (
              <p style={{ fontSize: '0.6rem', color: '#666', marginTop: '4px' }}>
                Note: Password may already be saved in MT5 terminal.
              </p>
            )}
          </div>
        </nav>

        <div className="sidebar-footer">
          <p style={{ fontSize: '0.7rem', color: '#666' }}>v2.4.1 MISSION CONTROL</p>
        </div>
      </aside>

      <main className="main-content">
        {activeTab === 'mission' ? (
          <>
            <div className="header">
              <div>
                <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '0.5rem' }}>Mission Dashboard</h1>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <span className={`status-badge ${status.is_running ? 'active' : 'idle'}`}>
                    {status.is_running ? 'BOT ACTIVE' : 'BOT IDLE'}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#666' }}>
                    PID: {status.pid || 'N/A'}
                  </span>
                  <span style={{
                    fontSize: '0.8rem',
                    padding: '4px 10px',
                    borderRadius: '20px',
                    background: status.account_status === 'Active' ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                    color: status.account_status === 'Active' ? '#00ff88' : '#888',
                    border: '1px solid rgba(255,255,255,0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}>
                    <TrendingUp size={12} /> MT5: {status.account_status}
                  </span>
                  <span style={{
                    fontSize: '0.8rem',
                    padding: '4px 10px',
                    borderRadius: '20px',
                    background: status.telegram_status === 'Connected' ? 'rgba(0, 242, 255, 0.1)' : 'rgba(255, 0, 85, 0.1)',
                    color: status.telegram_status === 'Connected' ? '#00f2ff' : '#ff0055',
                    border: '1px solid rgba(255,255,255,0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}>
                    <Activity size={12} /> Telegram: {status.telegram_status}
                  </span>
                  <span style={{
                    fontSize: '0.8rem',
                    padding: '4px 10px',
                    borderRadius: '20px',
                    background: status.polimata_retrains > 0 ? 'rgba(184, 134, 11, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                    color: status.polimata_retrains > 0 ? '#ffd700' : '#888',
                    border: '1px solid rgba(255,255,255,0.1)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '5px'
                  }}>
                    <Cpu size={12} /> Polimata: #{status.polimata_retrains} (Last: {status.last_retrain || 'N/A'})
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  background: 'rgba(255,255,255,0.03)',
                  padding: '6px 12px',
                  borderRadius: '12px',
                  border: '1px solid rgba(255,255,255,0.05)'
                }}>
                  <button
                    className={`btn ${basketConfig.enabled ? 'btn-success' : 'btn-dark'}`}
                    style={{
                      padding: '4px 12px',
                      fontSize: '0.75rem',
                      background: basketConfig.enabled ? 'rgba(0, 255, 136, 0.2)' : 'rgba(255,255,255,0.05)',
                      color: basketConfig.enabled ? '#00ff88' : '#666',
                      border: basketConfig.enabled ? '1px solid #00ff88' : '1px solid rgba(255,255,255,0.1)'
                    }}
                    onClick={handleToggleBasketLock}
                  >
                    <ShieldCheck size={14} /> {basketConfig.enabled ? 'LOCK ACTIVE' : 'LOCK OFF'}
                  </button>
                  <div style={{ width: '1px', height: '16px', background: 'rgba(255,255,255,0.1)' }}></div>
                  <span style={{ fontSize: '0.65rem', color: '#888', fontWeight: 600 }}>LOCK %:</span>
                  <input
                    type="text"
                    value={thresholdInput}
                    onChange={(e) => setThresholdInput(e.target.value)}
                    onBlur={handleUpdateThreshold}
                    onKeyDown={(e) => e.key === 'Enter' && handleUpdateThreshold()}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: '#00ff88',
                      width: '40px',
                      fontSize: '0.85rem',
                      fontWeight: 'bold',
                      textAlign: 'center',
                      outline: 'none',
                      padding: '0'
                    }}
                  />
                  <span style={{ fontSize: '0.9rem', color: '#00ff88', fontWeight: 'bold' }}>%</span>
                </div>

                <button
                  className={`btn ${status.mega_grid_active ? 'btn-primary' : 'btn-dark'}`}
                  onClick={handleToggleMegaGrid}
                  style={{
                    padding: '8px 16px',
                    fontSize: '0.8rem',
                    background: status.mega_grid_active ? 'rgba(0, 242, 255, 0.1)' : 'rgba(255,255,255,0.03)',
                    color: status.mega_grid_active ? '#00f2ff' : '#666',
                    border: status.mega_grid_active ? '1px solid #00f2ff' : '1px solid rgba(255,255,255,0.1)'
                  }}
                >
                  <Activity size={16} /> {status.mega_grid_active ? 'MEGA GRID' : 'GRID OFF'}
                </button>

                <button
                  className={`btn ${status.is_running ? 'btn-danger' : 'btn-success'}`}
                  onClick={status.is_running ? handleStop : handleStart}
                  style={{ padding: '10px 20px', fontWeight: 'bold' }}
                >
                  {status.is_running ? <Square size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
                  {status.is_running ? 'STOP BOT' : 'INICIAR BOT'}
                </button>
              </div>
            </div>

            <div className="stats-grid">
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ color: '#a0a0a0' }}>Equity</span>
                  <TrendingUp size={20} color="#00ff88" />
                </div>
                <h2 style={{ fontSize: '1.8rem' }}>${stats.equity.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h2>
                <p style={{ color: '#00ff88', fontSize: '0.8rem', marginTop: '0.5rem' }}>Balance: ${stats.balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              </div>

              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ color: '#a0a0a0' }}>Daily PnL</span>
                  <BarChart3 size={20} color="#00f2ff" />
                </div>
                <h2 style={{ fontSize: '1.8rem', color: stats.daily_pnl >= 0 ? '#00ff88' : '#ff0055' }}>
                  ${stats.daily_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                </h2>
                <p style={{ color: '#a0a0a0', fontSize: '0.8rem', marginTop: '0.5rem' }}>Total: ${stats.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}</p>
              </div>

              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ color: '#a0a0a0' }}>Margin Level</span>
                  <ShieldCheck size={20} color={stats.margin_level > 200 ? "#00ff88" : "#ffd700"} />
                </div>
                <h2 style={{ fontSize: '1.8rem' }}>{stats.margin_level.toFixed(2)}%</h2>
                <p style={{ color: '#a0a0a0', fontSize: '0.8rem', marginTop: '0.5rem' }}>Margin: ${stats.margin.toLocaleString()}</p>
              </div>

              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                  <span style={{ color: '#a0a0a0' }}>Free Margin</span>
                  <Zap size={20} color="#00f2ff" />
                </div>
                <h2 style={{ fontSize: '1.8rem' }}>${stats.free_margin.toLocaleString(undefined, { minimumFractionDigits: 2 })}</h2>
                <p style={{ color: '#a0a0a0', fontSize: '0.8rem', marginTop: '0.5rem' }}>{stats.active_trades} Active Trades</p>
              </div>
            </div>

            <section className="fleet-matrix" style={{ marginTop: '1.5rem' }}>
                <div className="card" style={{ border: '1px solid rgba(0, 242, 255, 0.15)', background: 'rgba(0, 242, 255, 0.02)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                        <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <Zap size={20} color="#00f2ff" /> FLEET CONTROL OMEGA+
                        </h3>
                        <div className="status-label" style={{ fontSize: '0.7rem', color: '#00f2ff', opacity: 0.6 }}>
                            BRIDGE PORT: 8080 (SECURE)
                        </div>
                    </div>

                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                            <thead>
                                <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.05)', color: '#666' }}>
                                    <th style={{ padding: '10px' }}>SYMBOL</th>
                                    <th style={{ padding: '10px' }}>STATUS</th>
                                    <th style={{ padding: '10px' }}>MODE</th>
                                    <th style={{ padding: '10px' }}>FORCED ROLE</th>
                                    <th style={{ padding: '10px' }}>SYNC</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.keys(fleetConfig).length > 0 ? Object.keys(fleetConfig).map((symbol) => (
                                    <tr key={symbol} style={{ borderBottom: '1px solid rgba(255,255,255,0.03)' }}>
                                        <td style={{ padding: '10px', fontWeight: 'bold' }}>{symbol}</td>
                                        <td style={{ padding: '10px' }}>
                                            <button 
                                                onClick={() => handleFleetToggle(symbol)}
                                                style={{
                                                    padding: '4px 10px',
                                                    borderRadius: '4px',
                                                    fontSize: '0.7rem',
                                                    fontWeight: 'bold',
                                                    background: fleetConfig[symbol].status === 'ON' ? 'rgba(0, 255, 136, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                                                    color: fleetConfig[symbol].status === 'ON' ? '#00ff88' : '#666',
                                                    border: `1px solid ${fleetConfig[symbol].status === 'ON' ? '#00ff88' : 'rgba(255,255,255,0.1)'}`,
                                                    cursor: 'pointer'
                                                }}
                                            >
                                                {fleetConfig[symbol].status}
                                            </button>
                                        </td>
                                        <td style={{ padding: '10px', fontSize: '0.75rem', opacity: 0.6 }}>
                                            {fleetConfig[symbol].strategy_mode}
                                        </td>
                                        <td style={{ padding: '10px' }}>
                                            <div style={{ display: 'flex', gap: '5px' }}>
                                                <button 
                                                    onClick={() => handleFleetModeAuto(symbol)}
                                                    style={{
                                                        padding: '2px 6px',
                                                        borderRadius: '3px',
                                                        fontSize: '0.65rem',
                                                        background: fleetConfig[symbol].strategy_mode === 'AUTO' ? '#00ff88' : 'transparent',
                                                        color: fleetConfig[symbol].strategy_mode === 'AUTO' ? '#000' : '#888',
                                                        border: '1px solid rgba(0, 255, 136, 0.2)',
                                                        cursor: 'pointer'
                                                    }}
                                                >AUTO</button>
                                                <button 
                                                    onClick={() => handleFleetRoleUpdate(symbol, 'NEM1')}
                                                    style={{
                                                        padding: '2px 6px',
                                                        borderRadius: '3px',
                                                        fontSize: '0.65rem',
                                                        background: fleetConfig[symbol].manual_nem_role === 'NEM1' ? '#00f2ff' : 'transparent',
                                                        color: fleetConfig[symbol].manual_nem_role === 'NEM1' ? '#000' : '#888',
                                                        border: '1px solid rgba(0, 242, 255, 0.2)',
                                                        cursor: 'pointer'
                                                    }}
                                                >N1</button>
                                                <button 
                                                    onClick={() => handleFleetRoleUpdate(symbol, 'NEM2')}
                                                    style={{
                                                        padding: '2px 6px',
                                                        borderRadius: '3px',
                                                        fontSize: '0.65rem',
                                                        background: fleetConfig[symbol].manual_nem_role === 'NEM2' ? '#ff4444' : 'transparent',
                                                        color: fleetConfig[symbol].manual_nem_role === 'NEM2' ? '#fff' : '#888',
                                                        border: '1px solid rgba(255, 68, 68, 0.2)',
                                                        cursor: 'pointer'
                                                    }}
                                                >N2</button>
                                            </div>
                                        </td>
                                        <td style={{ padding: '10px' }}>
                                            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#00ff88', boxShadow: '0 0 10px #00ff88' }}></div>
                                        </td>
                                    </tr>
                                )) : (
                                    <tr><td colSpan={5} style={{ padding: '20px', textAlign: 'center', opacity: 0.3 }}>Establishing Quantum Link...</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </section>

            {/* ALPHA HEAT MAP (NEW v6.3.2) */}
            <section className="alpha-heat-map" style={{ marginTop: '1.5rem' }}>
              <div className="card" style={{ border: '1px solid rgba(0, 255, 136, 0.15)', background: 'rgba(0, 255, 136, 0.02)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                    <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <Database size={20} color="#00ff88" /> MACHINE LEARNING: ALPHA HEAT MAP
                    </h3>
                    <div className="status-label" style={{ fontSize: '0.7rem', color: '#00ff88', opacity: 0.6 }}>
                        BAYESIAN LEVEL AFFINITY
                    </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '1rem' }}>
                    {Object.keys(affinityMap).length > 0 ? Object.keys(affinityMap).map((symbol) => {
                        const data = affinityMap[symbol];
                        const n1 = data.NEM1?.sum_r || 0;
                        const n2 = data.NEM2?.sum_r || 0;
                        const dom1 = Math.max(0, n1);
                        const dom2 = Math.max(0, n2);
                        const total = dom1 + dom2;
                        const per1 = total === 0 ? 50 : (dom1 / total) * 100;
                        const per2 = total === 0 ? 50 : (dom2 / total) * 100;
                        
                        let rec = "Neutral / Balanza";
                        let recColor = "#888";
                        if (n1 > n2 + 0.5) { rec = "Switch NEM1 (Trend)"; recColor = "#00ff88"; }
                        else if (n2 > n1 + 0.5) { rec = "Switch NEM2 (Antith)"; recColor = "#ff4444"; }

                        return (
                            <div key={symbol} style={{ background: 'rgba(255,255,255,0.02)', padding: '12px', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.05)' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 'bold', marginBottom: '8px' }}>
                                    <span>{symbol}</span>
                                    <span style={{ opacity: 0.4 }}>SCN: {(data.NEM1?.n || 0) + (data.NEM2?.n || 0)}</span>
                                </div>
                                <div style={{ fontSize: '0.7rem', display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                                    <span style={{ opacity: 0.5 }}>THESIS (N1)</span>
                                    <span style={{ color: n1 > 0 ? '#00ff88' : n1 < 0 ? '#ff4444' : '#666' }}>{n1.toFixed(2)}R</span>
                                </div>
                                <div style={{ fontSize: '0.7rem', display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                                    <span style={{ opacity: 0.5 }}>ANTITH (N2)</span>
                                    <span style={{ color: n2 > 0 ? '#00ff88' : n2 < 0 ? '#ff4444' : '#666' }}>{n2.toFixed(2)}R</span>
                                </div>
                                <div style={{ height: '3px', background: 'rgba(255,255,255,0.05)', borderRadius: '10px', display: 'flex', overflow: 'hidden' }}>
                                    <div style={{ width: `${per1}%`, background: '#00ff88', boxShadow: '0 0 5px #00ff88' }}></div>
                                    <div style={{ width: `${per2}%`, background: '#ff4444', boxShadow: '0 0 5px #ff4444' }}></div>
                                </div>
                                <div style={{ marginTop: '10px', textAlign: 'center', fontSize: '0.65rem', fontWeight: 'bold', color: recColor, textTransform: 'uppercase' }}>
                                    {rec}
                                </div>
                            </div>
                        );
                    }) : (
                        <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '20px', opacity: 0.3, fontSize: '0.8rem' }}>
                            🛰️ ESPERANDO INTELIGENCIA DE SCOUTS...
                        </div>
                    )}
                </div>
              </div>
            </section>

            <section className="market-activity">
              <div className="card" style={{ minHeight: '400px', overflowX: 'auto' }}>
                <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Activity size={20} color="#00f2ff" /> Recent Signals (Beta L-H-N)
                </h3>

                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#a0a0a0' }}>
                      <th style={{ padding: '12px' }}>Time</th>
                      <th style={{ padding: '12px' }}>Symbol</th>
                      <th style={{ padding: '12px' }}>Action</th>
                      <th style={{ padding: '12px' }}>Strategy</th>
                      <th style={{ padding: '12px' }}>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {signals.length > 0 ? signals.map((sig, i) => (
                      <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                        <td style={{ padding: '12px' }}>{sig.time}</td>
                        <td style={{ padding: '12px', fontWeight: 'bold' }}>{sig.symbol}</td>
                        <td style={{ padding: '12px' }}>
                          <span style={{
                            color: sig.type === 'BUY' ? '#00ff88' : '#ff0055',
                            fontWeight: 'bold',
                            padding: '2px 8px',
                            background: sig.type === 'BUY' ? 'rgba(0,255,136,0.1)' : 'rgba(255,0,85,0.1)',
                            borderRadius: '4px'
                          }}>
                            {sig.type}
                          </span>
                        </td>
                        <td style={{ padding: '12px', color: '#e0e0e0' }}>{sig.strategy}</td>
                        <td style={{ padding: '12px', color: '#666' }}>{sig.source}</td>
                      </tr>
                    )) : (
                      <tr>
                        <td colSpan={5} style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                          Waiting for live signals...
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </section>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '1.5rem' }}>
              <div className="card" style={{ minHeight: '350px' }}>
                <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <TrendingUp size={20} color="#00ff88" /> Active MT5 Positions
                </h3>
                {stats.active_positions && stats.active_positions.length > 0 ? (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
                    <thead>
                      <tr style={{ textAlign: 'left', borderBottom: '1px solid rgba(255,255,255,0.1)', color: '#666' }}>
                        <th style={{ padding: '8px' }}>Symbol</th>
                        <th style={{ padding: '8px' }}>Type</th>
                        <th style={{ padding: '8px' }}>Volume</th>
                        <th style={{ padding: '8px' }}>Profit</th>
                      </tr>
                    </thead>
                    <tbody>
                      {stats.active_positions.map((pos: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '8px', fontWeight: 'bold' }}>{pos.symbol}</td>
                          <td style={{ padding: '8px' }}>
                            <span style={{ color: pos.type === 'BUY' ? '#00ff88' : '#ff0055' }}>{pos.type}</span>
                          </td>
                          <td style={{ padding: '8px' }}>{pos.volume}</td>
                          <td style={{ padding: '8px', color: pos.profit >= 0 ? '#00ff88' : '#ff0055', fontWeight: 'bold' }}>
                            ${pos.profit.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>No open positions in MT5</div>
                )}
              </div>

              <div className="card" style={{ minHeight: '350px', background: '#0a0a0a' }}>
                <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <BarChart3 size={20} color="#ffd700" /> Recent MT5 History (Today)
                </h3>
                {stats.trade_history && stats.trade_history.length > 0 ? (
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                    <tbody>
                      {stats.trade_history.slice().reverse().map((deal: any, i: number) => (
                        <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                          <td style={{ padding: '6px', color: '#888' }}>{deal.time_open.split(' ')[1]}</td>
                          <td style={{ padding: '6px', fontWeight: 'bold' }}>{deal.symbol}</td>
                          <td style={{ padding: '6px' }}>{deal.volume}</td>
                          <td style={{ padding: '6px', color: deal.profit >= 0 ? '#00ff88' : '#ff0055' }}>
                            {deal.profit >= 0 ? '+' : ''}${deal.profit.toFixed(2)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>No trade history today</div>
                )}
              </div>
            </div>

            <section className="mt5-logs" style={{ marginTop: '1.5rem' }}>
              <div className="card" style={{ background: '#050505', border: '1px solid rgba(0, 242, 255, 0.2)' }}>
                <h3 style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <Database size={20} color="#00f2ff" /> Live Forex Logs (run_live)
                </h3>
                <div style={{
                  fontFamily: 'monospace',
                  fontSize: '0.75rem',
                  color: '#00f2ff',
                  height: '200px',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column-reverse',
                  background: 'rgba(0,0,0,0.3)',
                  padding: '10px',
                  borderRadius: '8px'
                }}>
                  {stats.last_log_lines && stats.last_log_lines.map((line: string, i: number) => (
                    <div key={i} style={{ marginBottom: '2px', opacity: i === 0 ? 1 : 0.7, borderLeft: '2px solid rgba(0,242,255,0.1)', paddingLeft: '8px' }}>
                      {line}
                    </div>
                  )).reverse()}
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="binance-view">
            <div className="header" style={{ marginBottom: '2rem' }}>
              <div>
                <h1 style={{ fontSize: '2.5rem', fontWeight: 800, marginBottom: '0.5rem', color: '#ffd700' }}>Binance Terminal</h1>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <span className={`status-badge ${binanceData.can_trade ? 'active' : 'idle'}`} style={{ background: binanceData.can_trade ? 'rgba(255, 215, 0, 0.1)' : 'rgba(255, 0, 85, 0.1)', color: binanceData.can_trade ? '#ffd700' : '#ff0055' }}>
                    {binanceData.can_trade ? 'STAGING: READY' : 'TRADING: DISABLED'}
                  </span>
                  <span style={{ fontSize: '0.8rem', color: '#666' }}>
                    Type: {binanceData.account_type}
                  </span>
                </div>
              </div>
            </div>

            <div className="stats-grid">
              <div className="card">
                <span style={{ color: '#a0a0a0', fontSize: '0.8rem' }}>USDT BALANCE</span>
                <h2 style={{ fontSize: '1.8rem', color: '#ffd700' }}>${(binanceData.balances?.USDT || 0).toFixed(4)}</h2>
              </div>
              <div className="card">
                <span style={{ color: '#a0a0a0', fontSize: '0.8rem' }}>ETH PRICE</span>
                <h2 style={{ fontSize: '1.8rem' }}>${(binanceData.prices?.ETH || 0).toLocaleString()}</h2>
                <p style={{ color: '#a0a0a0', fontSize: '0.7rem' }}>Bal: {(binanceData.balances?.ETH || 0).toFixed(6)} ETH</p>
              </div>
              <div className="card">
                <span style={{ color: '#a0a0a0', fontSize: '0.8rem' }}>SOL PRICE</span>
                <h2 style={{ fontSize: '1.8rem' }}>${(binanceData.prices?.SOL || 0).toLocaleString()}</h2>
                <p style={{ color: '#a0a0a0', fontSize: '0.7rem' }}>Bal: {(binanceData.balances?.SOL || 0).toFixed(4)} SOL</p>
              </div>
              <div className="card">
                <span style={{ color: '#a0a0a0', fontSize: '0.8rem' }}>BTC PRICE</span>
                <h2 style={{ fontSize: '1.8rem' }}>${(binanceData.prices?.BTC || 0).toLocaleString()}</h2>
                <p style={{ color: '#a0a0a0', fontSize: '0.7rem' }}>Bal: {(binanceData.balances?.BTC || 0).toFixed(8)} BTC</p>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginTop: '1.5rem' }}>
              <div className="card" style={{ minHeight: '300px' }}>
                <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px', color: '#ffd700' }}>
                  <Zap size={20} /> Polimata Binance Core
                </h3>
                {binanceData.active_positions.length > 0 ? (
                  binanceData.active_positions.map((pos: any, i: number) => (
                    <div key={i} style={{ padding: '15px', borderRadius: '8px', background: 'rgba(255, 255, 255, 0.02)', border: '1px solid rgba(255, 255, 255, 0.1)', marginBottom: '10px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 'bold' }}>{pos.symbol}</span>
                        <span style={{ color: '#00ff88' }}>COMPRA ACTIVA</span>
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#888', marginTop: '5px' }}>
                        Polimata DQN Neural Strategy
                      </div>
                    </div>
                  ))
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                    <Info size={32} style={{ marginBottom: '10px', opacity: 0.3 }} />
                    <p>No active positions on Binance</p>
                    <p style={{ fontSize: '0.7rem' }}>Scanning for Neural RL signals...</p>
                  </div>
                )}
              </div>

              <div className="card" style={{ minHeight: '300px', background: '#0a0a0a' }}>
                <h3 style={{ marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '10px', color: '#ffd700' }}>
                  <Database size={20} /> Live Logs (polimata_binance)
                </h3>
                <div style={{
                  fontFamily: 'monospace',
                  fontSize: '0.75rem',
                  color: '#00ff88',
                  height: '220px',
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column-reverse'
                }}>
                  {binanceData.last_log_lines.map((line: string, i: number) => (
                    <div key={i} style={{ marginBottom: '2px', opacity: i === 0 ? 1 : 0.7 }}>
                      {line}
                    </div>
                  )).reverse()}
                </div>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
