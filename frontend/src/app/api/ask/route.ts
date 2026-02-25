import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  console.log(' API Route /api/ask called');
  
  try {
    const bodyText = await request.text();
    console.log(' Raw body:', bodyText);
    
    const params = new URLSearchParams(bodyText);
    const file_id = params.get('file_id');
    const question = params.get('question');
    
    console.log(' Question recibida:', question);
    console.log(' File ID recibido:', file_id);
    
    if (!file_id || !question) {
      console.error('X Faltan campos:', { file_id, question });
      return NextResponse.json(
        { detail: 'file_id and question are required' },
        { status: 400 }
      );
    }
    
    const backendUrl = `${process.env.NEXT_PUBLIC_API_URL}/ask`;
    console.log(' Llamando a backend:', backendUrl);
    
    const backendBody = new URLSearchParams();
    backendBody.append('file_id', file_id);
    backendBody.append('question', question);
    
    const response = await fetch(backendUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: backendBody.toString(),
    });
    
    console.log(' Backend response status:', response.status);
    
    const data = await response.json();
    
    if (!response.ok) {
      return NextResponse.json(
        { detail: data.detail || 'Error processing question' },
        { status: response.status }
      );
    }
    
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('X Error in /api/ask:', error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Error interno del servidor' },
      { status: 500 }
    );
  }
}