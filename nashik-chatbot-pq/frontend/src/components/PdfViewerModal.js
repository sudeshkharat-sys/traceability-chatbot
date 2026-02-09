import React, { useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "./PdfViewerModal.css";

// Set up the worker
// Using unpkg with the exact version matching the library
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const HighlightOverlay = ({ bbox, pageHeight, scale }) => {
  if (!bbox || !pageHeight) return null;

  // Docling bbox is usually {l, b, r, t} with origin BOTTOMLEFT
  // React-PDF/Web is TOPLEFT
  const { l, b, r, t } = bbox;
  
  // Calculate dimensions
  // Left is just x * scale
  const left = l * scale;
  
  // Top in web = PageHeight - Top in PDF (since PDF Y goes up, Web Y goes down)
  // Adding a small vertical correction (-2) to shift the box UPWARD as requested
  const top = ((pageHeight - t) * scale) - 2;
  
  const width = (r - l) * scale;
  const height = ((t - b) * scale) + 2;

  const style = {
    position: 'absolute',
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`,
    backgroundColor: 'rgba(255, 255, 0, 0.3)', // Slightly more transparent
    border: '1px solid rgba(255, 200, 0, 0.8)', // Thinner border
    zIndex: 100, // Ensure it's on top of text layer
    pointerEvents: 'none', // Let clicks pass through
    borderRadius: '2px' // Rounded corners
  };

  return <div style={style} />;
};

const PdfViewerModal = ({ pdfUrl, initialScrollTo, onClose, isSidebar = false }) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(0.8);
  const [pageDimensions, setPageDimensions] = useState(null); // { width, height } (original PDF points)
  const [highlightBbox, setHighlightBbox] = useState(null);

  useEffect(() => {
    // Set initial page number and highlight from props
    if (initialScrollTo) {
      if (initialScrollTo.pageNumber) {
        setPageNumber(initialScrollTo.pageNumber);
      }
      if (initialScrollTo.boundingRect) {
        setHighlightBbox(initialScrollTo.boundingRect);
      }
    }
  }, [initialScrollTo]);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
  }

  // Called when the PAGE loads (not just document)
  // This gives us the original dimensions of the PDF page
  function onPageLoadSuccess(page) {
    setPageDimensions({
      width: page.originalWidth,
      height: page.originalHeight
    });
  }

  const changePage = (offset) => {
    setPageNumber((prevPageNumber) => Math.min(Math.max(1, prevPageNumber + offset), numPages));
    // Clear highlight if changing pages (optional, but usually highlights are per-page)
    // setHighlightBbox(null); 
  };

  const zoomIn = () => setScale(prev => Math.min(prev + 0.2, 2.0));
  const zoomOut = () => setScale(prev => Math.max(prev - 0.2, 0.6));

  const content = (
    <>
        <div className="pdf-modal-header">
          <div className="pdf-controls">
            <button 
              onClick={() => changePage(-1)} 
              disabled={pageNumber <= 1}
              className="control-btn"
            >
              Previous
            </button>
            <span className="page-info">
              Page {pageNumber} of {numPages || "--"}
            </span>
            <button 
              onClick={() => changePage(1)} 
              disabled={pageNumber >= numPages}
              className="control-btn"
            >
              Next
            </button>
            <span className="divider">|</span>
            <button onClick={zoomOut} className="control-btn">-</button>
            <span className="zoom-info">{Math.round(scale * 100)}%</span>
            <button onClick={zoomIn} className="control-btn">+</button>
          </div>
          <button className="pdf-modal-close" onClick={onClose}>
            &times; Close
          </button>
        </div>
        
        <div className="pdf-container">
          <Document
            file={pdfUrl}
            onLoadSuccess={onDocumentLoadSuccess}
            loading={<div className="loading">Loading PDF...</div>}
            error={<div className="error">Failed to load PDF. Check file path/CORS.</div>}
          >
            <div style={{ position: 'relative' }}>
                <Page 
                  pageNumber={pageNumber} 
                  scale={scale}
                  renderTextLayer={true}
                  renderAnnotationLayer={true}
                  onLoadSuccess={onPageLoadSuccess}
                />
                {/* Render highlight overlay if dimensions and bbox exist */}
                {pageDimensions && highlightBbox && highlightBbox.page_no === pageNumber && (
                    <HighlightOverlay 
                        bbox={highlightBbox} 
                        pageHeight={pageDimensions.height} 
                        scale={scale} 
                    />
                )}
            </div>
          </Document>
        </div>
    </>
  );

  if (isSidebar) {
      return (
          <div className="pdf-sidebar-container">
              {content}
          </div>
      );
  }

  return (
    <div className="pdf-modal-overlay">
      <div className="pdf-modal-content">
        {content}
      </div>
    </div>
  );
};

export default PdfViewerModal;