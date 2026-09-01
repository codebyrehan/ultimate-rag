import { useEffect, useRef } from 'react';

interface PdfViewerProps {
  documentId: string;
  filename: string;
  pageCount?: number;
}

export default function PdfViewer({ documentId, pageCount }: PdfViewerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const loadPdf = async () => {
      const pdfjsLib = await import('pdfjs-dist');
      pdfjsLib.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@4.2.67/build/pdf.worker.min.mjs`;

      const loadingTask = pdfjsLib.getDocument({
        url: `/documents/${documentId}/download`,
      });
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(1);

      const viewport = page.getViewport({ scale: 1.5 });
      const canvas = canvasRef.current;
      if (!canvas) return;
      const context = canvas.getContext('2d');
      if (!context) return;

      canvas.height = viewport.height;
      canvas.width = viewport.width;

      await page.render({
        canvasContext: context,
        viewport,
      }).promise;
    };

    loadPdf().catch((err) => {
      console.error('Failed to load PDF:', err);
    });
  }, [documentId]);

  return (
    <div className="border rounded-lg overflow-hidden">
      <canvas ref={canvasRef} className="w-full" />
      {pageCount && <p className="text-xs text-gray-500 p-2">Page 1 of {pageCount}</p>}
    </div>
  );
}
