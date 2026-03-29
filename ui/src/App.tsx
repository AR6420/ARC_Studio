import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLayout } from '@/components/layout/app-layout'
import { CampaignList } from '@/pages/campaign-list'

function CampaignNewPlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-sm font-medium text-muted-foreground">
        Campaign creation form coming soon.
      </p>
    </div>
  )
}

function CampaignDetailPlaceholder() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <p className="text-sm font-medium text-muted-foreground">
        Campaign detail view coming soon.
      </p>
    </div>
  )
}

function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/campaigns" replace />} />
      <Route element={<AppLayout title="Campaigns" />}>
        <Route path="/campaigns" element={<CampaignList />} />
        <Route path="/campaigns/new" element={<CampaignNewPlaceholder />} />
        <Route path="/campaigns/:id" element={<CampaignDetailPlaceholder />} />
      </Route>
    </Routes>
  )
}

export default App
