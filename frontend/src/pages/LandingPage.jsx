import { useState } from 'react'
import './LandingPage.css'

const MESSAGES = {
  idle: 'Not tested yet',
  checking: 'Checking...',
  connected: 'Database connected',
  failed: 'Database connection failed',
}

function LandingPage() {
  const [status, setStatus] = useState('idle')

  async function testConnection() {
    setStatus('checking')
    try {
      const response = await fetch('/api/health')
      setStatus(response.ok ? 'connected' : 'failed')
    } catch {
      setStatus('failed')
    }
  }

  return (
    <div className="landing">
      <header className="landing-header">
        <h1>Company News</h1>
      </header>
      <main className="connection-test">
        <button type="button" onClick={testConnection} disabled={status === 'checking'}>
          Test database connection
        </button>
        <p className={`connection-status ${status}`} role="status">
          {MESSAGES[status]}
        </p>
      </main>
    </div>
  )
}

export default LandingPage
