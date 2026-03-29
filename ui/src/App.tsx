import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/app-layout'
import { CampaignList } from '@/pages/campaign-list'
import NewCampaign from '@/pages/new-campaign'
import CampaignDetail from '@/pages/campaign-detail'

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/campaigns" replace />} />
      <Route element={<AppLayout title="Campaigns" />}>
        <Route path="/campaigns" element={<CampaignList />} />
        <Route path="/campaigns/new" element={<NewCampaign />} />
        <Route path="/campaigns/:id" element={<CampaignDetail />} />
      </Route>
    </Routes>
  )
}

export default App
