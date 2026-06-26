import { Inbox } from 'lucide-react';

type EmptyPanelProps = {
  message: string;
};

export function EmptyPanel({ message }: EmptyPanelProps) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-gray-200/60 bg-white py-16 px-6">
      <div className="flex size-12 items-center justify-center rounded-full bg-gray-100">
        <Inbox className="size-5 text-gray-400" />
      </div>
      <p className="mt-3 text-sm text-gray-500 text-center max-w-md">{message}</p>
    </div>
  );
}
