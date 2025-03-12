"use client";

import { useState, useEffect } from 'react';
import { useReportStore } from '@/lib/store';

type SidebarProps = {
  onSelectReport: (report: any) => void;
};

export default function Sidebar({ onSelectReport }: SidebarProps) {
  const reportStore = useReportStore();
  const [reports, setReports] = useState<any[]>([]);
  
  // Load reports from store
  useEffect(() => {
    setReports(reportStore.savedReports);
  }, [reportStore.savedReports]);
  
  // Format timestamp for display
  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    });
  };
  
  // Get icon for report type
  const getReportIcon = (type: string) => {
    switch (type) {
      case 'educational_content':
        return (
          <svg className="w-5 h-5 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
          </svg>
        );
      case 'sales_leads':
        return (
          <svg className="w-5 h-5 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
          </svg>
        );
      case 'financial_analysis':
        return (
          <svg className="w-5 h-5 text-purple-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
        );
      default:
        return (
          <svg className="w-5 h-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
        );
    }
  };
  
  return (
    <div className="w-64 h-full bg-white border-r border-gray-200 overflow-y-auto flex-shrink-0">
      <div className="p-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Saved Reports</h2>
        
        {/* Report list */}
        <div className="space-y-3">
          {reports.length === 0 ? (
            <p className="text-sm text-gray-500">No saved reports yet.</p>
          ) : (
            reports.map((report) => (
              <div
                key={report.id}
                className="p-3 bg-gray-50 rounded-lg hover:bg-gray-100 cursor-pointer transition-colors"
                onClick={() => onSelectReport(report)}
              >
                <div className="flex items-start">
                  <div className="flex-shrink-0 mt-1 mr-3">
                    {getReportIcon(report.type)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">
                      {report.query}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">
                      {formatDate(report.timestamp)}
                    </p>
                    <div className="mt-1 flex items-center">
                      <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                        {report.type.replace('_', ' ')}
                      </span>
                    </div>
                  </div>
                  
                  {/* Delete button */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      reportStore.deleteReport(report.id);
                    }}
                    className="ml-2 text-gray-400 hover:text-gray-600"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                      />
                    </svg>
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
        
        {/* Clear all button */}
        {reports.length > 0 && (
          <button
            onClick={() => reportStore.clearAllReports()}
            className="mt-4 w-full py-2 px-4 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Clear All Reports
          </button>
        )}
      </div>
    </div>
  );
}