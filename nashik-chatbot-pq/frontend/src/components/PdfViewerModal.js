import React, { useState, useEffect } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import "./PdfViewerModal.css";

// Set up the worker
// Using local worker file copied to public/ folder
// This avoids all CDN/CORS/Version mismatch issues
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.js';

const PdfViewerModal = ({ pdfUrl, initialScrollTo, onClose }) => {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1.0);

  useEffect(() => {
    // Set initial page number from props
    if (initialScrollTo && initialScrollTo.pageNumber) {
      setPageNumber(initialScrollTo.pageNumber);
    }
  }, [initialScrollTo]);

  function onDocumentLoadSuccess({ numPages }) {
    setNumPages(numPages);
  }

  const changePage = (offset) => {
    setPageNumber((prevPageNumber) => Math.min(Math.max(1, prevPageNumber + offset), numPages));
  };

  const zoomIn = () => setScale(prev => Math.min(prev + 0.2, 2.0));
  const zoomOut = () => setScale(prev => Math.max(prev - 0.2, 0.6));

  return (
    <div className="pdf-modal-overlay">
      <div className="pdf-modal-content">
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
            <Page 
              pageNumber={pageNumber} 
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </Document>
        </div>
      </div>
    </div>
  );
};

export default PdfViewerModal;