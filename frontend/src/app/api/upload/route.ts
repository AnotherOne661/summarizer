import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  console.log('API Route /api/upload called');
  
  try {
    const formData = await request.formData();
    console.log(' File recibido:', formData.get('file') ? 'Sí' : 'No');
    
    const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/upload`, {
      method: 'POST',
      body: formData,
    });
    
    console.log(' Backend response status:', response.status);
    
    const data = await response.json();
    
    if (!response.ok) {
      console.error(' Backend error:', data);
      return NextResponse.json(
        { detail: data.detail || 'Error processing PDF' },
        { status: response.status }
      );
    }
    
    console.log('Upload successful, file_id:', data.file_id);
    return NextResponse.json(data);
    
  } catch (error) {
    console.error(' Error in /api/upload:', error);
    return NextResponse.json(
      { detail: error instanceof Error ? error.message : 'Error interno del servidor' },
      { status: 500 }
    );
  }
}