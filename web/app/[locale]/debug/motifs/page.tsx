import { CategoryThumbnail } from "@/lib/design/CategoryThumbnail";

const CATEGORIES = [
  "movie", "performing_arts", "art", "nature", "senses", "lifestyle_food",
  "retail", "books_media", "tech", "tourism", "gender", "geopolitics",
  "lecture", "taiwan_japan", "business", "academic", "competition", "report"
];

export default function MotifsDebugPage() {
  return (
    <div className="p-10 bg-white flex flex-col gap-10">
      {CATEGORIES.map((cat) => (
        <div key={cat} className="flex flex-col border-b pb-8">
          <h2 className="text-xl font-bold mb-4">{cat}</h2>
          <div className="flex gap-4">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} id={`thumb-${cat}-${i}`} className="w-32 h-32 thumbnail" data-name={`${cat}_v${i}`}>
                <CategoryThumbnail id={`${cat}-seed${i}`} categories={[cat]} className="w-full h-full rounded-2xl" forceMotifIdx={i} />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
