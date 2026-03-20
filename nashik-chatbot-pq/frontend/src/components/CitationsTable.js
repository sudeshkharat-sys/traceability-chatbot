import React from "react";
import "./CitationsTable.css";

// Base URL for PDFs - use relative path so nginx proxies the request correctly
// PDFs are stored under documents/cop_standards_and_guidlines/ on the server
const BASE_PDF_URL = "/documents/cop_standards_and_guidlines/"; 

const CitationsTable = ({ citations, onOpenPdf }) => {
  if (!citations || citations.length === 0) return null;

  const handleOpenPdf = (citation) => {
      // Extract metadata regardless of format
      const metadata = citation.metadata || {};
      const docName = metadata.doc_name || citation.doc_name || "Unknown Document";
      
      const originalFileName = docName + (docName.toLowerCase().endsWith('.pdf') ? '' : '.pdf');
      const pdfUrl = `${BASE_PDF_URL}${encodeURIComponent(originalFileName)}`;
      
      // Extract Page Number
      let pageNum = metadata.page_label || metadata.page_number || citation.page_number;
      
      // Extract BBox from Docling structure if available
      let bbox = null;
      
      if (metadata.doc_items && metadata.doc_items.length > 0) {
         const firstItem = metadata.doc_items[0];
         if (firstItem.prov && firstItem.prov.length > 0) {
             if (!pageNum) pageNum = firstItem.prov[0].page_no;
             bbox = firstItem.prov[0].bbox;
         }
      }
      
      const targetPage = parseInt(pageNum) || 1;

      // Construct highlight/scroll data
      const scrollTo = {
          pageNumber: targetPage,
          // Pass the raw Docling bbox (l, b, r, t)
          boundingRect: bbox ? { ...bbox, page_no: targetPage } : null
      };

      if (onOpenPdf) {
          onOpenPdf(pdfUrl, scrollTo);
      }
  };

  // Deduplicate citations by doc_name + page number
  const seen = new Set();
  const uniqueCitations = citations.filter((citation) => {
    const metadata = citation.metadata || {};
    const docName = metadata.doc_name || citation.doc_name || "Unknown Document";
    let pageNum = metadata.page_label || metadata.page_number || citation.page_number;
    if (!pageNum && metadata.doc_items && metadata.doc_items.length > 0) {
      const firstItem = metadata.doc_items[0];
      if (firstItem.prov && firstItem.prov.length > 0) {
        pageNum = firstItem.prov[0].page_no;
      }
    }
    pageNum = pageNum || "N/A";
    const key = `${docName}::${pageNum}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

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
            {uniqueCitations.map((citation, index) => {
              const metadata = citation.metadata || {};
              let docName = metadata.doc_name || citation.doc_name || "Unknown Document";
              const displayName = docName.replace(/\.pdf$/i, "");

              let pageNum = metadata.page_label || metadata.page_number || citation.page_number;
              if (!pageNum && metadata.doc_items && metadata.doc_items.length > 0) {
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
                      onClick={() => handleOpenPdf(citation)}
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
    </div>
  );
};

export default CitationsTable;
