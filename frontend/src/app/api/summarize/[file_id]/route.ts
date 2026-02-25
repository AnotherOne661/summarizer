import { NextResponse } from 'next/server';

export async function POST(
  request: Request,
  { params }: { params: Promise <{ file_id: string }> }
) {
  console.log(' API Route /api/summarize called for file:');
  
  try {
    const { file_id } = await params;
    
    if (!file_id) {
      return NextResponse.json(
        { detail: 'file_id is required' },
        { status: 400 }
      );
    }
    
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/summarize/${file_id}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      return NextResponse.json(
        { detail: data.detail || 'Error generating summary' },
        { status: response.status }
      );
    }
    
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('X Error in /api/summarize:', error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Error interno del servidor' },
      { status: 500 }
    );
  }
}