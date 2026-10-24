import { Route, Routes } from 'react-router-dom'
import { Shell } from '@/components/Shell'
import ReviewQueue from '@/pages/ReviewQueue'
import Live from '@/pages/Live'
import Runs from '@/pages/Runs'
import Agents from '@/pages/Agents'
import Evals from '@/pages/Evals'
import Messenger from '@/pages/Messenger'

export default function App() {
  return (
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<ReviewQueue />} />
        <Route path="live" element={<Live />} />
        <Route path="runs/:runId?" element={<Runs />} />
        <Route path="agents" element={<Agents />} />
        <Route path="evals" element={<Evals />} />
        <Route path="messenger" element={<Messenger />} />
      </Route>
    </Routes>
  )
}
