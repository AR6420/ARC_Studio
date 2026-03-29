/**
 * NewCampaign page -- primary entry point for creating campaigns.
 *
 * Simple page wrapper that renders the CampaignForm.
 * On successful campaign creation, the form navigates to /campaigns/:id.
 */

import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'
import { CampaignForm } from '@/components/campaign/campaign-form'

export default function NewCampaign() {
  return (
    <div className="min-h-screen bg-background px-4 py-8 sm:px-6 lg:px-8">
      {/* Page header */}
      <div className="mx-auto max-w-3xl">
        <div className="mb-8 space-y-1">
          <Link
            to="/"
            className="mb-4 inline-flex items-center gap-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            Back to campaigns
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            New Campaign
          </h1>
          <p className="text-sm text-muted-foreground">
            Submit content for neural scoring and social simulation analysis.
          </p>
        </div>
      </div>

      <CampaignForm />
    </div>
  )
}
