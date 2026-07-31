import { Navigate, Route, Routes } from 'react-router'
import { Shell } from './app/Shell'
import { AllocationPage } from './features/allocation/AllocationPage'
import { CalibrationPage } from './features/calibration/CalibrationPage'
import { EquityPage } from './features/equity/EquityPage'
import { SimulatorPage } from './features/simulator/SimulatorPage'
import { PlannerPage } from './features/planner/PlannerPage'
import { KitchenSink } from './routes/KitchenSink'

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to="/planner" replace />} />
        <Route path="/planner" element={<PlannerPage />} />
        <Route path="/allocation" element={<AllocationPage />} />
        <Route path="/equity" element={<EquityPage />} />
        <Route path="/simulator" element={<SimulatorPage />} />
        <Route path="/calibration" element={<CalibrationPage />} />
        <Route path="/kitchen-sink" element={<KitchenSink />} />
      </Routes>
    </Shell>
  )
}
