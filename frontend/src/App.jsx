import { useState, useRef, useEffect } from 'react'
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import AutoAllocation from './pages/AutoAllocation.jsx'
import ReviewAutoAllocatedOrders from './pages/ReviewAutoAllocatedOrders.jsx'
import './App.css'

const COLORS = {
  primary: '#FFD700',
  secondary: '#000000',
  background: '#1a1a1a',
  text: '#ffffff',
  border: '#333',
}

function App() {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuContainerRef = useRef(null)
  const menuButtonRef = useRef(null)
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    const handleDocClick = (e) => {
      if (!menuOpen) return
      if (menuContainerRef.current && !menuContainerRef.current.contains(e.target) &&
          menuButtonRef.current && !menuButtonRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    document.addEventListener('mousedown', handleDocClick)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('mousedown', handleDocClick)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [menuOpen])

  const navTo = (path) => {
    navigate(path)
    setMenuOpen(false)
  }

  const pageTitle =
    location.pathname === '/auto-allocation' ? 'Auto Allocation' :
    location.pathname === '/review-auto-allocated-orders' ? 'Review Auto Allocated Orders' :
    'Delivery Schedules'

  return (
    <div className="app app-ct-style">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="app-header-left">
            <div style={{ position: 'relative', display: 'inline-block' }}>
              <button
                ref={menuButtonRef}
                onClick={() => setMenuOpen((o) => !o)}
                className="hamburger-btn"
                title="Open menu"
                aria-label="Open menu"
              >
                <span />
                <span />
                <span />
              </button>
              {menuOpen && (
                <div ref={menuContainerRef} className="app-menu-dropdown">
                  <div className="app-menu-header">
                    <strong>Menu</strong>
                    <button
                      type="button"
                      onClick={() => setMenuOpen(false)}
                      className="app-menu-close"
                      title="Close"
                      aria-label="Close menu"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="app-menu-body">
                    <button
                      type="button"
                      onClick={() => navTo('/')}
                      className={`app-menu-item ${location.pathname === '/' ? 'active' : ''}`}
                    >
                      Delivery Schedules
                    </button>
                    <button
                      type="button"
                      onClick={() => navTo('/auto-allocation')}
                      className={`app-menu-item ${location.pathname === '/auto-allocation' ? 'active' : ''}`}
                    >
                      Auto Allocation
                    </button>
                    <button
                      type="button"
                      onClick={() => navTo('/review-auto-allocated-orders')}
                      className={`app-menu-item ${location.pathname === '/review-auto-allocated-orders' ? 'active' : ''}`}
                    >
                      Review Auto Allocated Orders
                    </button>
                  </div>
                </div>
              )}
            </div>
            <div className="app-header-titles">
              <h1>Project SC</h1>
              <p>{pageTitle}</p>
            </div>
          </div>
        </div>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/auto-allocation" element={<AutoAllocation />} />
          <Route path="/review-auto-allocated-orders" element={<ReviewAutoAllocatedOrders />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
