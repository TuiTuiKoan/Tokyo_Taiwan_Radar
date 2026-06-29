"use client";

interface EventIntakeStepperProps {
  steps: number;
  current: number;
  labels?: string[];
}

export default function EventIntakeStepper({ steps, current, labels }: EventIntakeStepperProps) {
  const items = Array.from({ length: Math.max(steps, 1) }, (_, i) => i + 1);
  return (
    <div
      className="flex items-center justify-center py-2"
      role="group"
      aria-label={`Step ${current} of ${steps}`}
    >
      {items.map((step, idx) => {
        const isCompleted = step < current;
        const isCurrent = step === current;
        return (
          <div key={step} className="flex items-center">
            <div
              aria-current={isCurrent ? "step" : undefined}
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold leading-none transition-colors ${
                isCompleted
                  ? "border-green-600 bg-green-600 text-white"
                  : isCurrent
                    ? "border-green-600 bg-surface text-green-600"
                    : "border-line-strong bg-surface text-fg-muted"
              }`}
            >
              {isCompleted ? (
                <svg viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4" aria-hidden>
                  <path
                    fillRule="evenodd"
                    d="M16.7 5.3a1 1 0 0 1 0 1.4l-7.5 7.5a1 1 0 0 1-1.4 0L3.3 9.7a1 1 0 1 1 1.4-1.4l3.3 3.3 6.8-6.8a1 1 0 0 1 1.4 0z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : (
                step
              )}
            </div>
            {labels?.[idx] && (
              <span
                className={`ml-2 text-sm font-medium ${
                  isCurrent ? "text-green-600" : "text-fg-muted"
                }`}
              >
                {labels[idx]}
              </span>
            )}
            {idx < items.length - 1 && (
              <div
                aria-hidden
                className={`mx-1 h-0.5 w-10 transition-colors ${
                  step < current ? "bg-green-600" : "bg-gray-200 dark:bg-stone-700"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
