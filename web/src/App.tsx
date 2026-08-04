import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ChatApp } from './components/chat/ChatApp'
import { AdminPage } from './components/admin/AdminPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatApp />} />
        <Route path="/admin" element={<AdminPage />} />
      </Routes>
    </BrowserRouter>
  )
}
