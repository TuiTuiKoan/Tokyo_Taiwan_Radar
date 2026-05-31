import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { matchesLocation } from "@/lib/locationMarkers";
import { matchesCity, REGIONS_WITH_CITY } from "@/lib/regionPrefectures";
import { buildMonthRange, bucketCollected, bucketOngoing } from "@/lib/analytics/monthlyBuckets";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  try {
    // Auth check
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    const { data: roleRow } = await supabase
      .from("user_roles")
      .select("role")
      .eq("user_id", user.id)
      .single();
    if (!roleRow || roleRow.role !== "admin") {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }

    // Parse URL query params
    const { searchParams } = new URL(req.url);
    const fromMonth = searchParams.get("fromMonth");
    const toMonth = searchParams.get("toMonth");
    const location = searchParams.get("location");
    const city = searchParams.get("city");
    const category = searchParams.get("category");

    if (!fromMonth || !toMonth) {
      return NextResponse.json({ error: "Missing fromMonth or toMonth" }, { status: 400 });
    }

    // Check date format and 24 months limit
    const partsFrom = fromMonth.split("-");
    const partsTo = toMonth.split("-");
    if (partsFrom.length !== 2 || partsTo.length !== 2) {
      return NextResponse.json({ error: "Invalid date format" }, { status: 400 });
    }
    const y1 = parseInt(partsFrom[0], 10);
    const m1 = parseInt(partsFrom[1], 10);
    const y2 = parseInt(partsTo[0], 10);
    const m2 = parseInt(partsTo[1], 10);
    if (isNaN(y1) || isNaN(m1) || isNaN(y2) || isNaN(m2)) {
      return NextResponse.json({ error: "Invalid date format" }, { status: 400 });
    }
    const diff = (y2 - y1) * 12 + (m2 - m1) + 1;
    if (diff > 24) {
      return NextResponse.json({ error: "RangeTooWide" }, { status: 400 });
    }
    if (diff <= 0) {
      return NextResponse.json({ error: "toMonth must be after or equal to fromMonth" }, { status: 400 });
    }

    // Build start/end strings for filtering
    const rangeStart = `${fromMonth}-01`;
    const lastDay = new Date(Date.UTC(y2, m2, 0)).getUTCDate();
    const rangeEnd = `${toMonth}-${String(lastDay).padStart(2, "0")}`;

    // Load active and inactive events in the range
    // Loop paging to fetch all records (completely removing limit)
    let allEvents: any[] = [];
    let page = 0;
    const pageSize = 5000;
    let hasMore = true;

    while (hasMore) {
      const { data: pageData, error: fetchErr } = await supabase
        .from("events")
        .select("id, created_at, start_date, end_date, category, location_name, location_address, location_prefectures, is_active")
        .or(`start_date.lte.${rangeEnd},created_at.gte.${rangeStart}`)
        .range(page * pageSize, (page + 1) * pageSize - 1);

      if (fetchErr) {
        return NextResponse.json({ error: fetchErr.message }, { status: 500 });
      }

      if (pageData && pageData.length > 0) {
        allEvents = allEvents.concat(pageData);
        if (pageData.length < pageSize) {
          hasMore = false;
        } else {
          page++;
        }
      } else {
        hasMore = false;
      }
    }

    // Apply location filter (JS server-side post-filter)
    if (location && location !== "all") {
      allEvents = allEvents.filter(e => matchesLocation(e, location));
    }

    // Apply city sub-filter
    if (location && REGIONS_WITH_CITY.includes(location as any) && city && city !== "all") {
      allEvents = allEvents.filter(e => matchesCity(city, e.location_address, e.location_prefectures, location as any));
    }

    // Apply category filter
    if (category && category !== "all") {
      allEvents = allEvents.filter(e => {
        // Handle database single/array mapping or custom types
        const cats = (e as any).category;
        return cats && cats.includes(category);
      });
    }

    // Generate month buckets
    const monthsList = buildMonthRange(fromMonth, toMonth);
    const collectedMap = bucketCollected(allEvents, monthsList);
    const ongoingMap = bucketOngoing(allEvents, monthsList);

    const monthsResult = monthsList.map(m => {
      return {
        month: m,
        collected: collectedMap[m] || 0,
        ongoing: ongoingMap[m] || 0
      };
    });

    // Calculate overall totals
    const collectedCountObj = allEvents.filter(e => {
      if (!e.created_at) return false;
      const yymm = e.created_at.substring(0, 7);
      return monthsList.includes(yymm);
    });

    const ongoingCountObj = allEvents.filter(e => {
      if (!e.start_date) return false;
      const startStr = e.start_date;
      const endStr = e.end_date || startStr;
      return monthsList.some(m => {
        const startDayStr = `${m}-01`;
        const parts = m.split("-");
        const yr = parseInt(parts[0], 10);
        const mo = parseInt(parts[1], 10);
        const lDay = new Date(Date.UTC(yr, mo, 0)).getUTCDate();
        const endDayStr = `${m}-${String(lDay).padStart(2, "0")}`;
        return startStr <= endDayStr && endStr >= startDayStr;
      });
    });

    return NextResponse.json({
      months: monthsResult,
      totals: {
        collected: collectedCountObj.length,
        ongoing: ongoingCountObj.length
      }
    });

  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Internal Server Error" }, { status: 500 });
  }
}
