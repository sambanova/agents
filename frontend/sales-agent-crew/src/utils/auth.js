/**
 * Authentication utilities for managing access tokens
 */

// Get the access token from localStorage or use a default
export const getAccessToken = () => {
  return localStorage.getItem('access_token') || '';
};

// Set the access token programmatically
export const setAccessToken = (token) => {
  localStorage.setItem('access_token', token);
};

// Clear the access token
export const clearAccessToken = () => {
  localStorage.removeItem('access_token');
};

// Check if user has a token (not necessarily valid)
export const hasToken = () => {
  return !!localStorage.getItem('access_token');
};

// Get token for authentication header
export const getAuthHeader = () => {
  const token = getAccessToken();
  return token ? `Bearer ${token}` : '';
};

// Add auth header to provided headers
export const addAuthHeader = (headers = {}) => {
  const token = getAccessToken();
  if (token) {
    return {
      ...headers,
      'Authorization': `Bearer ${token}`
    };
  }
  return headers;
};