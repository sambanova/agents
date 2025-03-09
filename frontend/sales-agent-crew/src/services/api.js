// src/services/api.js
import axios from 'axios'
import { addAuthHeader } from '../utils/auth'

// Use environment variable for the API base URL
const API_URL = import.meta.env.PROD 
  ? `${window.location.origin}/api`  // Use the current origin in production
  : (import.meta.env.VITE_API_URL || 'http://localhost:8000')

// Create Axios instance with interceptor to add auth token to all requests
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Add interceptor to include auth token in every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * Unified query endpoint that handles both sales leads and research and financial analysis
 */
export const unifiedQuery = async (query, apiKeys) => {
  const headers = addAuthHeader({
    'Content-Type': 'application/json',
    'X-SambaNova-Key': apiKeys.sambanovaKey,
    'X-Exa-Key': apiKeys.exaKey,
    'X-Serper-Key': apiKeys.serperKey
  });
  
  const response = await fetch('/api/query', {
    method: 'POST',
    headers,
    body: JSON.stringify({ query })
  })

  if (!response.ok) {
    throw new Error('Failed to fetch results')
  }

  return response.json()
}

/**
 * Legacy function for backward compatibility
 */
export const generateLeads = async (query, apiKeys) => {
  const response = await unifiedQuery(query, apiKeys)
  if (response.type !== 'sales_leads') {
    throw new Error('Query was not identified as a sales lead request')
  }
  return response.results
}

/**
 * Generate research based on query
 */
export const generateResearch = async (query, apiKeys) => {
  const response = await unifiedQuery(query, apiKeys)
  if (response.type !== 'research') {
    throw new Error('Query was not identified as a research request')
  }
  return response.results
}

/**
 * Generate outreach content based on research/leads
 */
export const generateOutreach = async (data, apiKeys) => {
  const headers = addAuthHeader({
    'Content-Type': 'application/json',
    'X-SambaNova-Key': apiKeys.sambanovaKey
  });
  
  const response = await fetch('/api/outreach', {
    method: 'POST',
    headers,
    body: JSON.stringify(data)
  })

  if (!response.ok) {
    throw new Error('Failed to generate outreach content')
  }

  return response.json()
}

/**
 * Upload and process a document
 */
export const uploadDocument = async (file, sessionId) => {
  console.log('[api] uploadDocument called with sessionId:', sessionId)
  const formData = new FormData()
  formData.append('file', file)
  
  const headers = addAuthHeader({
    'Content-Type': 'multipart/form-data',
    'x-user-id': 'anonymous_user',
    'x-session-id': sessionId || ''
  });
  
  const response = await axios.post(
    `${API_URL}/upload`,
    formData,
    { headers }
  )
  
  return response.data
}

export default api
