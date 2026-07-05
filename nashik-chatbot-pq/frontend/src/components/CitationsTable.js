import React from "react";
import "./CitationsTable.css";

const CitationsTable = ({ citations }) => {
  if (!citations || citations.length === 0) return null;

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
      <div className="citations-table-wrapper">
        <table className="citations-table">
          <thead>
            <tr>
              <th>Document Name</th>
              <th>Page</th>
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
