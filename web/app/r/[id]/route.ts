import { NextResponse } from "next/server";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const base = process.env.NEXT_PUBLIC_BASE_URL ?? "";
  return NextResponse.redirect(`${base}/zh/events/${id}`, { status: 301 });
}
