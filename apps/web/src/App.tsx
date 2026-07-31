import { Navigate, Route, Routes } from 'react-router'
import { Shell } from './app/Shell'
import { AllocationPage } from './features/allocation/AllocationPage'
import { PlannerPage } from './features/planner/PlannerPage'
import { KitchenSink } from './routes/KitchenSink'

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/planner" replace />} />
        <Route path="/planner" element={<PlannerPage />} />
        <Route path="/allocation" element={<AllocationPage />} />
        <Route path="/kitchen-sink" element={<KitchenSink />} />
      </Routes>
    </Shell>
  )
}
