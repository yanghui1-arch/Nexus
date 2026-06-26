import { Loader2 } from 'lucide-react';

type SkeletonProps = {
  label: string;
};

export function ProposalTableSkeleton({ label }: SkeletonProps) {
  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white p-8">
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Loader2 className="size-4 animate-spin" />
        {label}
      </div>
    </div>
  );
}

export function FeatureTableSkeleton({ label }: SkeletonProps) {
  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white p-8">
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Loader2 className="size-4 animate-spin" />
        {label}
      </div>
    </div>
  );
}

export function ProposalDetailSkeleton({ label }: SkeletonProps) {
  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white p-8">
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Loader2 className="size-4 animate-spin" />
        {label}
      </div>
    </div>
  );
}

export function FeatureDetailSkeleton({ label }: SkeletonProps) {
  return (
    <div className="rounded-2xl border border-gray-200/60 bg-white p-8">
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <Loader2 className="size-4 animate-spin" />
        {label}
      </div>
    </div>
  );
}
