/**
 * New campaign page wrapper.
 *
 * Thin header rule + back link, then the form. No big hero title —
 * the form itself is the content.
 */

import { ArrowLeft } from 'lucide-react';
import { Link } from 'react-router-dom';
import { CampaignForm } from '@/components/campaign/campaign-form';

export default function NewCampaign() {
  return (
    <div className="flex flex-col gap-8">
      {/* Page heading */}
      <div className="mx-auto flex w-full max-w-[780px] items-end justify-between border-b border-border pb-4">
        <div className="flex flex-col gap-1">
          <Link
            to="/campaigns"
            className="inline-flex items-center gap-1 font-mono text-[0.64rem] tracking-[0.12em] text-muted-foreground uppercase transition-colors hover:text-foreground"
          >
            <ArrowLeft className="size-3" />
            Back
          </Link>
          <h1 className="text-[1.15rem] font-semibold tracking-[-0.01em] text-foreground">
            New Campaign
          </h1>
          <p className="font-mono text-[0.68rem] tracking-[0.08em] text-muted-foreground uppercase">
            Neural scoring · social simulation · optimization loop
          </p>
        </div>
      </div>

      <CampaignForm />
    </div>
  );
}
