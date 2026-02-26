import { NextResponse } from 'next/server';

type Params = Promise<{ file_id: string }>;

export async function GET(
  request: Request,
  { params }: { params: Params }
) {
  try {
    const { file_id } = await params;
    
    if (!file_id) {
      return NextResponse.json(
        { detail: 'file_id is required' },
        { status: 400 }
      );
    }

    const backendUrl = `${process.env.NEXT_PUBLIC_API_URL}/extract-full/${file_id}`;
    const response = await fetch(backendUrl);
    
    if (!response.ok) {
      const errorData = await response.json();
      return NextResponse.json(
        { detail: errorData.detail || 'Error extracting full text' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error in /api/extract/[file_id]:', error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    );
  }
}