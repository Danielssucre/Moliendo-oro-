import React, { useState, useEffect } from 'react';
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
    risk_label: ""
  });
  const [signals, setSignals] = useState<Signal[]>([]);
  const [creds, setCreds] = useState({ account: '', password: '', server: 'FTMO-Demo' });
  const [risk, setRisk] = useState(0.4);

  const [discoveredAccounts, setDiscoveredAccounts] = useState<any[]>([]);
  const [showNewAccount, setShowNewAccount] = useState(false);

  useEffect(() => {
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

        // Auto-select first account if nothing is selected yet
        if (data.length > 0 && !creds.account) {
          const first = data[0];
          setCreds({ account: String(first.account), server: first.server, password: '' });
          setShowNewAccount(false);

          // Inform backend of selection
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
      } catch (err) {
        console.error("Failed to connect to backend");
      }
    };

    fetchConfig();
    fetchAccounts();
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

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

          <div style={{ display: 'flex', gap: '1rem' }}>
            <button
              className={`btn ${status.mega_grid_active ? 'btn-gold' : 'btn-dark'}`}
              onClick={handleToggleMegaGrid}
              style={{
                background: status.mega_grid_active ? 'linear-gradient(135deg, #ffd700, #b8860b)' : 'rgba(255,255,255,0.05)',
                color: status.mega_grid_active ? '#000' : '#888',
                fontWeight: 700,
                border: status.mega_grid_active ? 'none' : '1px solid rgba(255,255,255,0.1)'
              }}
            >
              {status.mega_grid_active ? <Activity size={18} /> : <Activity size={18} style={{ opacity: 0.5 }} />}
              {status.mega_grid_active ? 'MEGA GRID: ON' : 'MEGA GRID: OFF'}
            </button>

            <button
              className={`btn ${status.is_running ? 'btn-danger' : 'btn-primary'}`}
              onClick={status.is_running ? handleStop : handleStart}
              disabled={!creds.account || (!creds.password && showNewAccount)}
            >
              {status.is_running ? <Square size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}
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
      </main>
    </div>
  );
}

export default App;
