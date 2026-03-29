import { Routes, Route } from 'react-router-dom'
import NewCampaign from '@/pages/new-campaign'

function App() {
  return (
    <Routes>
      <Route
        path="/"
        element={
          <div className="min-h-screen bg-background text-foreground flex items-center justify-center">
            <h1 className="text-3xl font-bold">Nexus Sim</h1>
          </div>
        }
      />
      <Route path="/campaigns/new" element={<NewCampaign />} />
    </Routes>
  )
}

export default App
