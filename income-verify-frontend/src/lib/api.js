import axios from 'axios'
import { turnstileToken } from '@/lib/turnstile'

export const API_BASE = `${import.meta.env.VITE_BACKEND_URL || ''}/api`
export const api = axios.create({ baseURL: API_BASE })

// The requests that start paid OCR and model work carry a Turnstile token (the backend checks it when configured).
const GUARDED = [/^\/applications$/, /^\/applications\/[^/]+\/documents$/, /^\/samples\/[^/]+$/]
api.interceptors.request.use(async config => {
  if (config.method === 'post' && GUARDED.some(re => re.test(config.url))) {
    const token = await turnstileToken()
    if (token) config.headers['cf-turnstile-response'] = token
  }
  return config
})

export const fileUrl = documentId => `${API_BASE}/documents/${documentId}/file`
export const exportUrl = (applicationId, format) => `${API_BASE}/applications/${applicationId}/export?format=${format}`

export const errorMessage = err => {
  if (err?.response?.data?.message) return err.response.data.message
  if (err?.code === 'ERR_NETWORK') return 'Cannot reach the server. Check that the backend is running and try again.'
  return err?.message || 'Something went wrong'
}
