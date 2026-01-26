import { Routes, Route } from 'react-router-dom'
import Dashboard from './pages/Dashboard.jsx'
import './App.css'

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Project SC - Schedule Administration</h1>
        <p>Ordering & Delivery Schedule Management</p>
      </header>
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
