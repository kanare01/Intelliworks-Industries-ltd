/**
 * Real API Service Client
 * Attaches Supabase Bearer token to all authorized requests.
 * Connects to Flask backend /api endpoints.
 */
import { supabase } from './supabase';

const API_BASE = '/api';

export async function apiRequest(endpoint, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {})
  };

  // Obtain verified session token from Supabase Auth
  if (supabase) {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
      }
    } catch (err) {
      console.warn('Could not retrieve Supabase session for request', err);
    }
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers
  });

  const contentType = response.headers.get('content-type');
  let data;
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = { message: await response.text() };
  }

  if (!response.ok) {
    const error = new Error(data.message || data.error || `HTTP error ${response.status}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

// API methods
export const api = {
  getHealth: () => apiRequest('/health'),
  getAcademicPolicy: () => apiRequest('/academic-policy'),
  getPublicSettings: () => apiRequest('/settings'),
  getMe: () => apiRequest('/me'),
  updateProfile: (data) => apiRequest('/profile', { method: 'PUT', body: JSON.stringify(data) }),

  // Assignments
  createAssignment: (data) => apiRequest('/assignments', { method: 'POST', body: JSON.stringify(data) }),
  listAssignments: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiRequest(`/assignments${query ? `?${query}` : ''}`);
  },
  getAssignment: (id) => apiRequest(`/assignments/${id}`),
  claimAssignment: (id) => apiRequest(`/assignments/${id}/claim`, { method: 'POST' }),
  submitDeliverable: (id, data) => apiRequest(`/assignments/${id}/submit`, { method: 'POST', body: JSON.stringify(data) }),
  requestRevision: (id, data) => apiRequest(`/assignments/${id}/revision`, { method: 'POST', body: JSON.stringify(data) }),
  approveAssignment: (id) => apiRequest(`/assignments/${id}/approve`, { method: 'POST' }),
  cancelAssignment: (id) => apiRequest(`/assignments/${id}/cancel`, { method: 'POST' }),

  // Messaging
  getMessages: (id) => apiRequest(`/assignments/${id}/messages`),
  sendMessage: (id, text) => apiRequest(`/assignments/${id}/messages`, { method: 'POST', body: JSON.stringify({ message: text }) }),

  // Financial & Reviews
  getTransactions: () => apiRequest('/transactions'),
  getWithdrawals: () => apiRequest('/withdrawals'),
  requestWithdrawal: (data) => apiRequest('/withdrawals', { method: 'POST', body: JSON.stringify(data) }),
  submitReview: (data) => apiRequest('/reviews', { method: 'POST', body: JSON.stringify(data) }),

  // Disputes
  openDispute: (id, data) => apiRequest(`/assignments/${id}/dispute`, { method: 'POST', body: JSON.stringify(data) }),
  listDisputes: () => apiRequest('/disputes'),

  // Notifications
  getNotifications: () => apiRequest('/notifications'),
  markNotificationRead: (id) => apiRequest(`/notifications/${id}/read`, { method: 'PUT' }),
  markAllNotificationsRead: () => apiRequest('/notifications/read-all', { method: 'PUT' }),

  // Referrals
  getReferrals: () => apiRequest('/referrals'),

  // Admin
  getAdminMetrics: () => apiRequest('/admin/metrics'),
  getAdminUsers: (params = {}) => {
    const query = new URLSearchParams(params).toString();
    return apiRequest(`/admin/users${query ? `?${query}` : ''}`);
  },
  updateUserStatus: (id, status) => apiRequest(`/admin/users/${id}/status`, { method: 'PUT', body: JSON.stringify({ status }) }),
  resolveDispute: (id, data) => apiRequest(`/admin/disputes/${id}/resolve`, { method: 'POST', body: JSON.stringify(data) }),
  approveWithdrawal: (id) => apiRequest(`/admin/withdrawals/${id}/approve`, { method: 'POST' }),
  rejectWithdrawal: (id, data) => apiRequest(`/admin/withdrawals/${id}/reject`, { method: 'POST', body: JSON.stringify(data) }),
  getAuditLogs: (limit = 50) => apiRequest(`/admin/audit-logs?limit=${limit}`),
  updateSettings: (key, value) => apiRequest('/admin/settings', { method: 'PUT', body: JSON.stringify({ key, value }) })
};
