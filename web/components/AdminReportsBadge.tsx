interface Props {
  initialCount: number;
}

export default function AdminReportsBadge({ initialCount }: Props) {
  if (initialCount === 0) return null;
  return (
    <span className="inline-flex items-center justify-center min-w-[1.1rem] h-4 px-1 text-[10px] font-bold rounded-full bg-red-500 text-white leading-none">
      {initialCount}
    </span>
  );
}
