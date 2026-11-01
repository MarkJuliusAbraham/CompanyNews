import { useEffect, useRef, useState } from 'react'
import './LandingPage.css'

const USERNAME_KEY = 'company-news-username'
const GUEST_TICKERS_KEY = 'company-news-guest-tickers'
const GUEST_LIMIT = 3
const TRADINGVIEW_EMBED_URL = 'https://s3.tradingview.com/external-embedding'
const STOCK_WIDGET = {
  script: 'embed-widget-mini-symbol-overview.js',
  options: { dateRange: '1M', height: 200 },
}
const FINANCIALS_WIDGET = {
  script: 'embed-widget-financials.js',
  options: { displayMode: 'regular', height: 720 },
}
const SUGGESTIONS = ['Apple', 'Microsoft', 'Nvidia', 'Unity Software']

const MESSAGES = {
  idle: 'Not tested yet',
  checking: 'Checking...',
  connected: 'Database connected',
  failed: 'Database connection failed',
}

function readStored(key) {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function writeStored(key, value) {
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  } catch {
    // The page still works for this visit without saved data.
  }
}

function readGuestTickers() {
  try {
    const tickers = JSON.parse(readStored(GUEST_TICKERS_KEY))
    return Array.isArray(tickers) ? tickers.slice(0, GUEST_LIMIT) : []
  } catch {
    return []
  }
}

const dateTimeFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short',
})

function formatDateTime(value) {
  return dateTimeFormat.format(new Date(value))
}

const timeFormat = new Intl.DateTimeFormat(undefined, { timeStyle: 'short' })
const dayFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
})

const TODAY_LABEL = dayFormat.format(new Date())

function dayLabel(value) {
  const date = new Date(value)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  return dayFormat.format(date)
}

// Articles arrive newest first, so each day's articles are already together.
function groupByDay(articles) {
  const groups = []
  for (const article of articles) {
    const label = dayLabel(article.published_at)
    const current = groups[groups.length - 1]
    if (current?.label === label) current.articles.push(article)
    else groups.push({ label, articles: [article] })
  }
  return groups
}

function monogram(name) {
  return name.trim().charAt(0).toUpperCase()
}

async function fetchGuestCompanies(tickers) {
  const response = await fetch('/api/companies/guest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tickers }),
  })
  if (!response.ok) throw new Error('Could not load companies')
  return response.json()
}

function Navbar({ username, onSignIn, onSignOut }) {
  const [name, setName] = useState('')
  const [signingIn, setSigningIn] = useState(false)
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    setSigningIn(true)
    setError('')
    try {
      const response = await fetch('/api/users/sign-in', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: name }),
      })
      if (response.status === 422) {
        setError('Use 2 to 30 letters, numbers, dashes or underscores.')
        return
      }
      if (!response.ok) throw new Error('Sign-in failed')
      const user = await response.json()
      setName('')
      onSignIn(user.username)
    } catch {
      setError('Could not sign in. Try again.')
    } finally {
      setSigningIn(false)
    }
  }

  return (
    <nav className="navbar">
      <div className="brand">
        <h1>Company News</h1>
        <p>{TODAY_LABEL}</p>
      </div>
      {username ? (
        <div className="navbar-account">
          <span>{username}</span>
          <button type="button" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      ) : (
        <form className="navbar-account" onSubmit={submit}>
          {error && (
            <span className="connection-status failed" role="alert">
              {error}
            </span>
          )}
          <input
            aria-label="Username"
            placeholder="Username"
            autoComplete="username"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" disabled={signingIn || name.trim() === ''}>
            {signingIn ? 'Signing in...' : 'Sign in'}
          </button>
        </form>
      )}
    </nav>
  )
}

function TradingViewWidget({ ticker, script: scriptName, options }) {
  const container = useRef(null)

  useEffect(() => {
    const element = container.current
    const script = document.createElement('script')
    script.src = `${TRADINGVIEW_EMBED_URL}/${scriptName}`
    script.async = true
    script.textContent = JSON.stringify({
      symbol: ticker,
      width: '100%',
      ...options,
      colorTheme: 'dark',
      isTransparent: true,
      locale: 'en',
    })
    element.appendChild(script)
    return () => {
      element.replaceChildren()
    }
  }, [ticker, scriptName, options])

  return <div className="market-widget tradingview-widget-container" ref={container} />
}

function LandingPage() {
  const [username, setUsername] = useState(() => readStored(USERNAME_KEY))

  function changeUser(next) {
    writeStored(USERNAME_KEY, next)
    setUsername(next)
  }

  return (
    <div className="landing">
      <Navbar username={username} onSignIn={changeUser} onSignOut={() => changeUser(null)} />
      <CompanyTracker key={username ?? 'guest'} username={username} />
    </div>
  )
}

function CompanyTracker({ username }) {
  const [status, setStatus] = useState('idle')
  const [companies, setCompanies] = useState([])
  const [query, setQuery] = useState('')
  const [results, setResults] = useState({ query: '', companies: [] })
  const [picked, setPicked] = useState(null)
  const [adding, setAdding] = useState(false)
  const [selected, setSelected] = useState(null)
  const [articles, setArticles] = useState(null)
  const [error, setError] = useState('')
  const [showFinancials, setShowFinancials] = useState(false)

  const search = query.trim()
  const showResults = !picked && search !== '' && results.query === search
  const guestAtLimit = !username && companies.length >= GUEST_LIMIT

  useEffect(() => {
    let request
    if (username) {
      request = fetch(`/api/users/${encodeURIComponent(username)}/companies`).then((response) => {
        if (!response.ok) throw new Error('Could not load companies')
        return response.json()
      })
    } else {
      const tickers = readGuestTickers()
      request = tickers.length > 0 ? fetchGuestCompanies(tickers) : Promise.resolve([])
    }
    request
      .then((loaded) => {
        setCompanies(loaded)
        if (loaded.length > 0) selectCompany(loaded[0])
      })
      .catch(() => setError('Could not load companies.'))
  }, [username])

  // Wait for a pause in typing, and cancel any search that's out of date.
  useEffect(() => {
    if (picked || search === '') return undefined
    const controller = new AbortController()
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/companies/search?query=${encodeURIComponent(search)}`, {
          signal: controller.signal,
        })
        if (!response.ok) throw new Error('Search failed')
        setResults({ query: search, companies: await response.json() })
      } catch (searchError) {
        if (searchError.name !== 'AbortError') setError('Could not search companies.')
      }
    }, 250)
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [search, picked])

  async function testConnection() {
    setStatus('checking')
    try {
      const response = await fetch('/api/health')
      setStatus(response.ok ? 'connected' : 'failed')
    } catch {
      setStatus('failed')
    }
  }

  async function selectCompany(company) {
    setSelected(company)
    setArticles(null)
    setError('')
    try {
      const response = await fetch(`/api/companies/${company.id}/articles`)
      if (!response.ok) throw new Error('Could not load articles')
      setArticles(await response.json())
    } catch {
      setError('Could not load articles.')
    }
  }

  function pickFirstOnEnter(event) {
    if (event.key !== 'Enter' || picked) return
    event.preventDefault()
    if (showResults && results.companies.length > 0) pickResult(results.companies[0])
  }

  function pickResult(company) {
    setPicked(company)
    setQuery(`${company.name} (${company.ticker})`)
  }

  function changeQuery(event) {
    setPicked(null)
    setError('')
    setQuery(event.target.value)
  }

  async function addForUser(ticker) {
    const response = await fetch(`/api/users/${encodeURIComponent(username)}/companies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticker }),
    })
    if (!response.ok) throw new Error('Could not add company')
    const company = await response.json()
    setCompanies((current) => [...current.filter(({ id }) => id !== company.id), company])
    return company
  }

  async function addForGuest(ticker) {
    const tickers = [...new Set([...companies.map((company) => company.ticker), ticker])]
    const updated = await fetchGuestCompanies(tickers)
    const company = updated.find((item) => item.ticker === ticker)
    if (!company) throw new Error('Could not add company')
    writeStored(GUEST_TICKERS_KEY, JSON.stringify(updated.map((item) => item.ticker)))
    setCompanies(updated)
    return company
  }

  async function addCompany(event) {
    event.preventDefault()
    setAdding(true)
    setError('')
    try {
      const add = username ? addForUser : addForGuest
      const company = await add(picked.ticker)
      setPicked(null)
      setQuery('')
      await selectCompany(company)
    } catch {
      setError('Could not add that company.')
    } finally {
      setAdding(false)
    }
  }

  async function removeCompany(company) {
    setError('')
    try {
      if (username) {
        const response = await fetch(
          `/api/users/${encodeURIComponent(username)}/companies/${company.id}`,
          { method: 'DELETE' },
        )
        if (!response.ok) throw new Error('Could not remove company')
      } else {
        const tickers = companies.map(({ ticker }) => ticker)
        const remaining = tickers.filter((ticker) => ticker !== company.ticker)
        writeStored(GUEST_TICKERS_KEY, JSON.stringify(remaining))
      }
      setCompanies((current) => current.filter(({ id }) => id !== company.id))
      if (selected?.id === company.id) {
        const next = companies.find(({ id }) => id !== company.id)
        if (next) selectCompany(next)
        else {
          setSelected(null)
          setArticles(null)
        }
      }
    } catch {
      setError('Could not remove that company.')
    }
  }

  return (
    <main className="tracker">
      <aside className="sidebar">
        <form className="add-company" onSubmit={addCompany}>
          <div className="company-search">
            <input
              aria-label="Search companies"
              placeholder={guestAtLimit ? 'Remove a company to add another' : 'Search name or ticker'}
              autoComplete="off"
              value={query}
              onChange={changeQuery}
              onKeyDown={pickFirstOnEnter}
              disabled={guestAtLimit}
            />
            {showResults && !guestAtLimit && (
              <ul className="company-results">
                {results.companies.map((company) => (
                  <li key={company.ticker}>
                    <button type="button" onClick={() => pickResult(company)}>
                      <span>{company.name}</span>
                      <span className="ticker">{company.ticker}</span>
                    </button>
                  </li>
                ))}
                {results.companies.length === 0 && (
                  <li className="no-results">No listed companies found</li>
                )}
              </ul>
            )}
          </div>
          <button type="submit" className="primary" disabled={!picked || adding || guestAtLimit}>
            {adding ? 'Adding...' : 'Add Company'}
          </button>
        </form>

        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}

        <div className="watchlist-heading">
          <h2>Watchlist</h2>
          <span>{username ? companies.length : `${companies.length}/${GUEST_LIMIT}`}</span>
        </div>

        {companies.length === 0 && <p className="watchlist-empty">No companies yet.</p>}

        {companies.length > 0 && (
          <ul className="company-list">
            {companies.map((company) => (
              <li key={company.id} className={selected?.id === company.id ? 'active' : ''}>
                <button
                  type="button"
                  className="company-select"
                  aria-pressed={selected?.id === company.id}
                  onClick={() => selectCompany(company)}
                >
                  <span className="monogram" aria-hidden="true">
                    {monogram(company.name)}
                  </span>
                  <span className="company-text">
                    <span className="company-name">{company.name}</span>
                    <span className="ticker">{company.ticker}</span>
                  </span>
                </button>
                <button
                  type="button"
                  className="remove-company"
                  aria-label={`Remove ${company.name}`}
                  onClick={() => removeCompany(company)}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}

        {!username && (
          <p className="guest-notice">
            You&apos;re browsing as a guest. Your {GUEST_LIMIT}-company watchlist is saved only in
            this browser. Sign in to track more.
          </p>
        )}

        <div className="status-check">
          <button type="button" onClick={testConnection} disabled={status === 'checking'}>
            Test database connection
          </button>
          <span className={`connection-status ${status}`} role="status">
            {status === 'idle' ? '' : MESSAGES[status]}
          </span>
        </div>
      </aside>

      <section className="articles" aria-live="polite">
        {!selected && (
          <div className="empty-state">
            <h2>Build your morning brief</h2>
            <p>Add a company to your watchlist, and its news collects here every morning.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((suggestion) => (
                <button
                  type="button"
                  key={suggestion}
                  onClick={() => setQuery(suggestion)}
                  disabled={guestAtLimit}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {selected && (
          <>
            <header className="articles-header">
              <span className="monogram large" aria-hidden="true">
                {monogram(selected.name)}
              </span>
              <div>
                <h2>{selected.name}</h2>
                <p>
                  <span className="ticker">{selected.ticker}</span>
                  {selected.last_fetched_at
                    ? `Updated ${formatDateTime(selected.last_fetched_at)}`
                    : 'Not updated yet'}
                </p>
              </div>
            </header>

            <div className="market-panels">
              <section className="market-panel stock-panel">
                <h3>Stock</h3>
                <TradingViewWidget key={selected.ticker} ticker={selected.ticker} {...STOCK_WIDGET} />
              </section>
              <details
                className="market-panel financials-panel"
                open={showFinancials}
                onToggle={(event) => setShowFinancials(event.currentTarget.open)}
              >
                <summary>Debt &amp; Financials</summary>
                {showFinancials && (
                  <TradingViewWidget
                    key={selected.ticker}
                    ticker={selected.ticker}
                    {...FINANCIALS_WIDGET}
                  />
                )}
              </details>
            </div>

            <div className="news-heading">
              <h3>News</h3>
              <p>
                Sourced from{' '}
                <a href="https://gnews.io" target="_blank" rel="noreferrer">
                  GNews
                </a>
                . Each story links to its original publisher.
              </p>
            </div>

            {articles === null && !error && (
              <div className="skeleton" aria-label="Loading articles">
                <span />
                <span />
                <span />
              </div>
            )}

            {articles?.length === 0 && (
              <div className="no-articles">
                <h3>Nothing new yet</h3>
                <p>
                  {selected.last_fetched_at
                    ? 'No recent articles were found. New ones are fetched every morning.'
                    : 'News could not be fetched yet. It will be tried again in the morning.'}
                </p>
              </div>
            )}

            {articles?.length > 0 &&
              groupByDay(articles).map((group, groupIndex) => (
                <section className="day" key={group.label}>
                  <h3>{group.label}</h3>
                  <ul className="news-list">
                    {group.articles.map((article, index) => (
                      <li
                        key={article.url}
                        className={groupIndex === 0 && index === 0 ? 'lead' : ''}
                      >
                        <span className="article-source">{article.source}</span>
                        <a href={article.url} target="_blank" rel="noreferrer">
                          {article.title}
                        </a>
                        <time dateTime={article.published_at}>
                          {timeFormat.format(new Date(article.published_at))}
                        </time>
                      </li>
                    ))}
                  </ul>
                </section>
              ))}
          </>
        )}
      </section>
    </main>
  )
}

export default LandingPage
