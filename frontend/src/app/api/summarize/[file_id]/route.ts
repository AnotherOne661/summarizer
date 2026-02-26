import { NextResponse } from 'next/server';
import { Agent, fetch as undiciFetch } from 'undici';

type Params = Promise<{ file_id: string }>;

export async function POST(
  request: Request,
  { params }: { params: Params }
) {
  console.log('API Route /api/summarize called');
  
  try {
    const { file_id } = await params;
    
    if (!file_id) {
      return NextResponse.json(
        { detail: 'file_id is required' },
        { status: 400 }
      );
    }

    const agent = new Agent({
      connectTimeout: 0,
      headersTimeout: 0,
      bodyTimeout: 0,
    });

    const backendUrl = `${process.env.NEXT_PUBLIC_API_URL}/summarize/${file_id}`;
    console.log('Calling backend:', backendUrl);
    
    const response = await undiciFetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      dispatcher: agent,
    });
    
    console.log('Backend response status:', response.status);
    
    const data: any = await response.json();
    
    if (!response.ok) {
      console.error(' Backend error:', data);
      return NextResponse.json(
        { detail: (data && data.detail) || 'Error generating summary' },
        { status: response.status }
      );
    }
    
    console.log(' Summary generated successfully');
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Error in /api/summarize:', error);
    if (error instanceof DOMException && error.name === 'AbortError') {
      return NextResponse.json(
        { detail: 'Request aborted' },
        { status: 504 }
      );
    }
    
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 }
    );
  }
}