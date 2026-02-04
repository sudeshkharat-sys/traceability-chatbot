import React, { useState } from "react";
import "./CitationsTable.css";
import PdfViewerModal from "./PdfViewerModal";

// Base URL for the Apache server hosting the PDFs
// We add /documents/ because that is where we created the folder in Apache htdocs
const BASE_PDF_URL = "http://localhost:8081/documents/"; 

const CitationsTable = ({ citations }) => {
  const [selectedPdf, setSelectedPdf] = useState(null);

  if (!citations || citations.length === 0) return null;

  const handleOpenPdf = (docName, pageNum) => {
      const originalFileName = docName + (docName.toLowerCase().endsWith('.pdf') ? '' : '.pdf');
      const pdfUrl = `${BASE_PDF_URL}${encodeURIComponent(originalFileName)}`;
      
      // Construct highlight/scroll data
      // For now, we mainly rely on page number. 
      // Highlighting logic can be extended here if bbox conversion is reliable.
      const scrollTo = {
          pageNumber: parseInt(pageNum) || 1,
          boundingRect: { x1: 0, y1: 0, x2: 0, y2: 0, width: 0, height: 0, pageNumber: parseInt(pageNum) || 1 }
      };

      setSelectedPdf({
          url: pdfUrl,
          scrollTo: scrollTo
      });
  };

  const handleClosePdf = () => {
      setSelectedPdf(null);
  };

  return (
    <div className="citations-container">
      <h4 className="citations-title">Sources & Citations</h4>
      <div className="citations-table-wrapper">
        <table className="citations-table">
          <thead>
            <tr>
              <th>Document Name</th>
              <th>Page</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {citations.map((citation, index) => {
              // Extract metadata regardless of format (full object or simplified)
              const metadata = citation.metadata || {};
              let docName = metadata.doc_name || citation.doc_name || "Unknown Document";
              
              // Remove .pdf extension for cleaner display
              const displayName = docName.replace(/\.pdf$/i, "");
              
              // Extract Page Number: Check flat fields first, then deep Docling structure
              let pageNum = metadata.page_label || metadata.page_number || citation.page_number;
              
              if (!pageNum && metadata.doc_items && metadata.doc_items.length > 0) {
                 // Try to find page_no in the first item's provenance
                 const firstItem = metadata.doc_items[0];
                 if (firstItem.prov && firstItem.prov.length > 0) {
                     pageNum = firstItem.prov[0].page_no;
                 }
              }
              
              pageNum = pageNum || "N/A";

              return (
                <tr key={index}>
                  <td className="doc-name-cell" title={displayName}>
                    {displayName}
                  </td>
                  <td className="page-cell">{pageNum}</td>
                  <td className="action-cell">
                    <button 
                      onClick={() => handleOpenPdf(docName, pageNum)}
                      className="open-pdf-btn"
                    >
                      Open PDF
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {selectedPdf && (
          <PdfViewerModal 
            pdfUrl={selectedPdf.url} 
            initialScrollTo={selectedPdf.scrollTo}
            onClose={handleClosePdf}
          />
      )}
    </div>
  );
};

export default CitationsTable;
