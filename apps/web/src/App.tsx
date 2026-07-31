import { Navigate, Route, Routes } from 'react-router'
import { KitchenSink } from './routes/KitchenSink'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/kitchen-sink" replace />} />
      <Route path="/kitchen-sink" element={<KitchenSink />} />
    </Routes>
  )
}
