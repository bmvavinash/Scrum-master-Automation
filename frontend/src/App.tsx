import { NavLink, Route, Routes } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Meetings from './pages/Meetings'
import Jira from './pages/Jira'
import Git from './pages/Git'
import Chat from './pages/Chat'
import './App.css'

function App() {
  return (
    <div className="min-h-screen bg-[rgb(var(--bg-page))] text-[rgb(var(--text-main))]">
      <header className="border-b bg-white/90 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-4 flex items-center justify-between">
          <div className="font-semibold text-brand-700 text-lg">Scrum Automation</div>
          <nav className="flex gap-6 text-sm">
            <NavLink to="/" end className={({isActive})=> isActive ? 'text-brand-700 font-medium' : 'text-gray-600 hover:text-brand-700'}>Dashboard</NavLink>
            <NavLink to="/meetings" className={({isActive})=> isActive ? 'text-brand-700 font-medium' : 'text-gray-600 hover:text-brand-700'}>Meetings</NavLink>
            <NavLink to="/jira" className={({isActive})=> isActive ? 'text-brand-700 font-medium' : 'text-gray-600 hover:text-brand-700'}>Jira</NavLink>
            <NavLink to="/git" className={({isActive})=> isActive ? 'text-brand-700 font-medium' : 'text-gray-600 hover:text-brand-700'}>Git</NavLink>
            <NavLink to="/chat" className={({isActive})=> isActive ? 'text-brand-700 font-medium' : 'text-gray-600 hover:text-brand-700'}>Bot Chat</NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/meetings" element={<Meetings />} />
          <Route path="/jira" element={<Jira />} />
          <Route path="/git" element={<Git />} />
          <Route path="/chat" element={<Chat />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
