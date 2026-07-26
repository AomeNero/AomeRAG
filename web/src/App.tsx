import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { ChatApp } from './components/chat/ChatApp'
import { AdminPage } from './components/admin/AdminPage'
import { FeedbackPage } from './components/admin/FeedbackPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<ChatApp />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/admin/feedback" element={<FeedbackPage />} />
      </Routes>
    </BrowserRouter>
  )
}
