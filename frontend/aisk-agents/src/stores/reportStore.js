import { defineStore } from 'pinia'

export const useReportStore = defineStore('reportStore', {
  state: () => ({
    savedReports: []
  }),
  actions: {
    saveReport(type, query, results) {
      try {
        const report = {
          id: Date.now(),
          type,                   // 'educational_content' or 'sales_leads'
          query,                  // The user's search query
          timestamp: new Date().toISOString(),
          results                 // The actual report / leads data
        }
        
        // Add to the start of the array
        this.savedReports.unshift(report)
        
        // Persist to localStorage
        this.persistReports()
        console.log('Report saved successfully:', report.id)
      } catch (error) {
        console.error('Error saving report:', error)
      }
    },

    loadSavedReports() {
      try {
        const saved = localStorage.getItem('savedReports')
        if (saved) {
          this.savedReports = JSON.parse(saved)
          console.log('Loaded reports:', this.savedReports.length)
        }
      } catch (error) {
        console.error('Error loading saved reports:', error)
        this.savedReports = []
      }
    },

    persistReports() {
      try {
        localStorage.setItem('savedReports', JSON.stringify(this.savedReports))
        console.log('Reports persisted to localStorage')
      } catch (error) {
        console.error('Error persisting reports:', error)
      }
    },

    deleteReport(reportId) {
      try {
        this.savedReports = this.savedReports.filter(r => r.id !== reportId)
        this.persistReports()
        console.log('Report deleted:', reportId)
      } catch (error) {
        console.error('Error deleting report:', error)
      }
    },

    /**
     * NEW: Clear all reports
     */
    clearAllReports() {
      try {
        this.savedReports = []
        this.persistReports()
        console.log('All reports cleared!')
      } catch (error) {
        console.error('Error clearing all reports:', error)
      }
    }
  }
})
